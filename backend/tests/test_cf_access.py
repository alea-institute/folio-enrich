"""Offline Access annotation contracts using real, locally generated RSA keys."""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.api import auth
from app.api.routes import gold
from app.config import settings

TEAM = "folio-test.cloudflareaccess.com"
AUD = "annotation-application"
EMAIL = "reviewer@example.com"


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def jwks(signing_key):
    key = json.loads(RSAAlgorithm.to_jwk(signing_key.public_key()))
    key.update(kid="test-key", alg="RS256", use="sig")
    return {"keys": [key]}


@pytest.fixture
def token(signing_key):
    def make(*, changes=None, omit=(), algorithm="RS256", kid="test-key"):
        claims = {"aud": [AUD], "iss": f"https://{TEAM}", "exp": int(time.time()) + 300,
                  "email": EMAIL, "sub": "local-test-subject"}
        claims.update(changes or {})
        for claim in omit:
            claims.pop(claim, None)
        key = signing_key if algorithm == "RS256" else ("offline-test-secret" if algorithm == "HS256" else "")
        return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": kid})
    return make


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "annotation_token", "annotation-secret")
    monkeypatch.setattr(settings, "admin_token", "admin-secret")
    monkeypatch.setattr(settings, "cf_access_team_domain", TEAM)
    monkeypatch.setattr(settings, "cf_access_aud", AUD)
    monkeypatch.setattr(settings, "cf_access_allowed_emails", f"other@example.com, {EMAIL.upper()}")
    # Stop at the real handler boundary; never write committed gold or session files.
    mutation = AsyncMock(return_value={"session_id": "offline-test"})
    monkeypatch.setattr(gold._gold_store, "create_validation_session", mutation)
    return mutation


@pytest.fixture
def verifier(monkeypatch, jwks):
    instance = auth.CfAccessVerifier(team_domain=TEAM, aud=AUD,
        allowed_emails=f"other@example.com, {EMAIL.upper()}", jwks_fetcher=lambda: jwks)
    monkeypatch.setattr(auth, "_configured_cf_access_verifier", lambda *args: instance)
    return instance


async def mutate(client, assertion=None, origin="http://test", **extra):
    headers = dict(extra)
    if assertion is not None:
        headers["Cf-Access-Jwt-Assertion"] = assertion
    if origin is not None:
        headers["Origin"] = origin
    return await client.post("/gold/validation-sessions", json={"slug": "offline"}, headers=headers)


async def test_valid_access_authorizes_mutation(client, token, verifier, configured):
    response = await mutate(client, token())
    assert response.status_code == 201
    configured.assert_awaited_once_with("offline")


@pytest.mark.parametrize("scenario", ["audience", "issuer", "expired", "email", "missing-email",
    "missing-exp", "missing-iss", "missing-aud", "HS256", "none", "unknown-kid", "tampered"])
async def test_rejected_assertions(client, token, verifier, configured, scenario):
    options = {
        "audience": {"changes": {"aud": "other-app"}},
        "issuer": {"changes": {"iss": "https://other.cloudflareaccess.com"}},
        "expired": {"changes": {"exp": int(time.time()) - 60}},
        "email": {"changes": {"email": "intruder@example.com"}},
        "missing-email": {"omit": ("email",)},
        "missing-exp": {"omit": ("exp",)},
        "missing-iss": {"omit": ("iss",)},
        "missing-aud": {"omit": ("aud",)},
        "HS256": {"algorithm": "HS256"},
        "none": {"algorithm": "none"},
        "unknown-kid": {"kid": "absent"},
        "tampered": {},
    }[scenario]
    assertion = token(**options)
    if scenario == "tampered":
        header, payload, signature = assertion.split(".")
        raw = bytearray(jwt.utils.base64url_decode(signature))
        raw[0] ^= 1
        assertion = f"{header}.{payload}.{jwt.utils.base64url_encode(bytes(raw)).decode()}"
    assert (await mutate(client, assertion)).status_code == 403
    configured.assert_not_awaited()


@pytest.mark.parametrize("origin", ["https://sibling.example", None, "null", "http://test/path"])
async def test_access_requires_same_origin(client, token, verifier, configured, origin):
    response = await mutate(client, token(), origin=origin)
    assert response.status_code == 403
    assert response.json()["detail"] == "Same-origin request required"
    configured.assert_not_awaited()


@pytest.mark.parametrize("assertion", [None, "forged-header"])
async def test_direct_origin_cannot_mutate_without_credentials(client, verifier, configured, assertion):
    assert (await mutate(client, assertion)).status_code == 403
    configured.assert_not_awaited()


async def test_access_only_configuration_closes_open_mode(client, token, verifier, monkeypatch):
    monkeypatch.setattr(settings, "annotation_token", "")
    monkeypatch.setattr(settings, "admin_token", "")
    assert (await mutate(client)).status_code == 403
    assert (await mutate(client, token())).status_code == 201


async def test_jwks_failure_denies(client, token, verifier, configured):
    def unavailable():
        raise OSError("offline")
    verifier._fetch = unavailable
    assert (await mutate(client, token())).status_code == 403
    configured.assert_not_awaited()


async def test_expired_jwks_fetch_failure_does_not_use_stale_keys(client, token, verifier):
    assert (await mutate(client, token())).status_code == 201
    verifier._jwks_fetched_at = 0
    def unavailable():
        raise OSError("offline")
    verifier._fetch = unavailable
    assert (await mutate(client, token())).status_code == 403


async def test_unknown_kid_refreshes_once_then_denies(client, token, verifier, jwks):
    calls = []
    def fetch():
        calls.append(1)
        return jwks
    verifier._fetch = fetch
    assert (await mutate(client, token(kid="absent"))).status_code == 403
    assert len(calls) == 2  # initial fetch, then exactly one refresh


async def test_rotated_key_is_accepted_after_refresh(client, token, verifier, jwks):
    rotated = json.loads(json.dumps(jwks))
    rotated["keys"][0]["kid"] = "rotated"
    responses = iter([jwks, rotated])
    verifier._fetch = lambda: next(responses)
    assert (await mutate(client, token())).status_code == 201
    assert (await mutate(client, token(kid="rotated"))).status_code == 201


async def test_jwks_is_cached(client, token, verifier, jwks):
    calls = []
    def fetch():
        calls.append(1)
        return jwks
    verifier._fetch = fetch
    for _ in range(2):
        assert (await mutate(client, token())).status_code == 201
    assert len(calls) == 1


@pytest.mark.parametrize("missing", ["cf_access_team_domain", "cf_access_aud", "cf_access_allowed_emails"])
async def test_partial_settings_disable_access(client, token, verifier, monkeypatch, missing):
    monkeypatch.setattr(settings, missing, "")
    assert (await mutate(client, token())).status_code == 403
    assert (await mutate(client, **{"X-Annotation-Token": "annotation-secret"})).status_code == 201
    monkeypatch.setattr(settings, "annotation_token", "")
    monkeypatch.setattr(settings, "admin_token", "")
    assert (await mutate(client)).status_code == 201


@pytest.mark.parametrize("header,credential", [("X-Annotation-Token", "annotation-secret"),
    ("X-Admin-Token", "admin-secret")])
async def test_break_glass_headers_still_work(client, token, verifier, header, credential):
    assert (await mutate(client, token(changes={"aud": "wrong"}), origin=None,
                         **{header: credential})).status_code == 201


@pytest.mark.parametrize("mode", ["cloudflare-access", "token-header", "admin-header", "token-cookie", "open", "unauthenticated", "invalid-access"])
async def test_access_status_never_leaks_credentials(client, token, verifier, monkeypatch, mode):
    headers = {}
    via, email, authenticated = None, None, False
    assertion = token()
    if mode == "cloudflare-access":
        headers = {"Cf-Access-Jwt-Assertion": assertion}
        via, email, authenticated = "cloudflare-access", EMAIL, True
    elif mode in {"token-header", "admin-header", "token-cookie"}:
        header, value = {
            "token-header": ("X-Annotation-Token", "annotation-secret"),
            "admin-header": ("X-Admin-Token", "admin-secret"),
            "token-cookie": ("Cookie", "folio_annotation_access=annotation-secret"),
        }[mode]
        headers = {header: value}
        via, authenticated = "token", True
    elif mode == "open":
        for name in ("cf_access_team_domain", "cf_access_aud", "cf_access_allowed_emails", "annotation_token", "admin_token"):
            monkeypatch.setattr(settings, name, "")
        via, authenticated = "open", True
    elif mode == "invalid-access":
        headers = {"Cf-Access-Jwt-Assertion": token(changes={"aud": "wrong"})}
    response = await client.get("/gold/access", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"authenticated": authenticated, "via": via, "email": email}
    for secret in (assertion, "annotation-secret", "admin-secret", "offline-test-secret"):
        assert secret not in response.text
    assert response.headers["cache-control"] == "no-store"


async def test_second_allowed_email_and_case_insensitivity(client, token, verifier):
    assertion = token(changes={"email": "OTHER@EXAMPLE.COM"})
    assert (await mutate(client, assertion)).status_code == 201
    status = await client.get("/gold/access", headers={"Cf-Access-Jwt-Assertion": assertion})
    assert status.json()["email"] == "OTHER@EXAMPLE.COM"
