---
title: Cloudflare Access sign-in for proposition annotation - Plan
type: feat
date: 2026-10-04
status: completed
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-plan-bootstrap
execution: code
---

# Cloudflare Access sign-in for proposition annotation - Plan

## Goal Capsule

- **Objective:** Damien opens the plain propositions-dev link, signs in with his email through Cloudflare Access, and can annotate. He never handles an annotation token.
- **Product authority:** Damien Riehl, decision record `folio-enrich-2026-10-04-0213-annotation-signin` ("Cloudflare Access with email sign-in; token kept as break-glass").
- **Open blockers:** none.
- **Execution profile:** code on branch `feat/cf-access-annotation` (agent-implemented, verified, merged). The orchestrator does the Cloudflare and Hetzner configuration. DEV only; the propositions PROD instance is unchanged.

## Product Contract

### Requirements

- R1. A gold mutation is authorized by a valid Cloudflare Access login for an allowed email. The scoped annotation token and the admin token keep working as before (break-glass).
- R2. A Cloudflare Access login is valid only after the server verifies its signature against the team's published keys (RS256 only), plus issuer, audience, expiry, and an email claim in the configured allow-list. The header's presence alone grants nothing.
- R3. A mutation authorized through Cloudflare Access also passes the existing same-origin check (request `Origin` must match `Host`). The browser attaches Cloudflare's login automatically, so this is cookie-like credential handling.
- R4. When the Access settings are unset, behavior is exactly as today, including the open local mode when no token is configured either.
- R5. The Propositions toolbar shows who is signed in when authorized through Cloudflare Access, instead of asking for an access code.
- R6. Requests that reach the origin without passing Cloudflare (the sslip.io hostname or the bare IP) cannot mutate gold without a token. R2 guarantees this.

## Planning Contract

### Key Technical Decisions

- KTD1. **Port the verifier pattern from the mootloop repo** (`src/mootloop/web/security.py`, `CfAccessVerifier`): PyJWT with `algorithms=["RS256"]`, a JWKS cached from `https://<team>/cdn-cgi/access/certs`, a key looked up by `kid` with one refresh on a miss, and `aud`/`iss`/`exp` pinned. The allow-list holds one or more emails, compared case-insensitively. A fetch failure denies the request; nothing fails open. Governs R2.
- KTD2. **Settings:** `cf_access_team_domain`, `cf_access_aud` and `cf_access_allowed_emails` (comma-separated), each with the `FOLIO_ENRICH_` prefix. Access is enabled only when all three are set. Governs R4.
- KTD3. **Dependency:** `pyjwt[crypto]`, pinned in `backend/pyproject.toml` and `uv.lock` and logged in `THIRD-PARTY.md` (MIT; the `cryptography` package is Apache-2.0/BSD). Governs R2.
- KTD4. **Status endpoint:** `GET /gold/access` returns `{"authenticated": bool, "via": "cloudflare-access"|"token"|"open"|null, "email": str|null}`. It never echoes a credential. Governs R5.

## Implementation Units

### U1. Access verification in the annotation gate

- **Files:** `backend/app/api/auth.py`, `backend/app/config.py`, `backend/app/api/routes/gold.py`, `backend/pyproject.toml`, `backend/uv.lock`, `THIRD-PARTY.md`, `backend/tests/test_cf_access.py` (new).
- **Approach:** per KTD1–KTD4. The verifier is an injectable singleton so tests can substitute keys. `require_annotation` gains the Access header path (`Cf-Access-Jwt-Assertion`), subject to the same Origin/Host check as the cookie path.
- **Test scenarios:** with a locally generated RSA key and JWKS:
  - A valid token authorizes a gold mutation.
  - Each of these is rejected: a wrong audience, wrong issuer, expired token, email not on the allow-list, missing email, HS256 or `none` algorithm, unknown `kid` after the one refresh, and a tampered signature.
  - A JWKS fetch failure denies.
  - A valid token with a cross-site Origin is rejected.
  - With Access unset, behavior is unchanged: the existing token tests pass, and the open local mode stays open.
  - `GET /gold/access` reports each mode without leaking credentials.

### U2. Toolbar sign-in state

- **Files:** `frontend/index.html`, `docs/annotation-access.md`.
- **Approach:** on loading the Propositions tab, call `GET /gold/access`. When `via` is `cloudflare-access`, show "Signed in as <email> (Cloudflare Access)" and hide the access-code field behind Session tools. The doc moves Cloudflare Access from "long-term" to the primary method and keeps the token link as break-glass.

## Verification Contract

- `cd backend && .venv/bin/python -m pytest tests/ -q` passes; the byte-neutral harness is unchanged.
- After deploy, check the orchestrator's DEV evidence:
  - An unauthenticated request to propositions-dev.damienriehl.com is redirected to Cloudflare Access sign-in.
  - A gold mutation to the sslip.io fallback hostname without a token gets 403.
  - `GET /gold/access` through the sslip.io hostname reports unauthenticated.

## Definition of Done

- U1–U2 are merged with tests passing, and DEV is deployed with the Access app, the proxied DNS and the three settings.
- The verification evidence above is recorded in the PR or the closing report.
