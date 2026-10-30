"""U4 regressions: ruler caching, cheap active-job counting, bounded LLM fan-out,
semantic-ruler gating and candidate generation, and JWKS refresh rate-limiting."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from app.api import auth
from app.models.document import CanonicalText, DocumentInput, TextChunk
from app.models.job import Job, JobStatus
from app.pipeline.stages import entity_ruler_stage as ers
from app.services.concept import llm_concept_identifier as lci
from app.services.embedding.providers.local import LocalEmbeddingProvider
from app.services.embedding import service as embedding_service_mod
from app.services.embedding.service import EmbeddingService
from app.services.entity_ruler import semantic_ruler as sr
from app.services.entity_ruler.semantic_ruler import SemanticEntityRuler
from app.services.folio.folio_service import FOLIOConcept, LabelInfo
from app.storage import job_store as js
from app.storage.job_store import JobStore


def _job(text: str) -> Job:
    job = Job()
    job.result.canonical_text = CanonicalText(
        full_text=text,
        chunks=[TextChunk(text=text, start_offset=0, end_offset=len(text), chunk_index=0)],
    )
    return job


# ── Defect 2: FOLIO EntityRuler built once per ontology version ────────────


def _labels(*names: str) -> tuple[dict, dict]:
    single, multi = {}, {}
    for i, name in enumerate(names):
        concept = FOLIOConcept(
            iri=f"https://example.org/R{i}", preferred_label=name.title(),
            alternative_labels=[], definition="", branch="Area of Law", parent_iris=[],
        )
        info = LabelInfo(concept=concept, label_type="preferred", matched_label=name)
        single[name] = info
        multi[name] = [info]
    return single, multi


class _FakeFolio:
    ontology_id = "folio"

    def __init__(self, names):
        self.labels, self.multi = _labels(*names)

    def get_all_labels(self):
        return self.labels

    def get_all_labels_multi(self):
        return self.multi


@pytest.fixture
def fake_folio(monkeypatch):
    monkeypatch.setattr(ers, "_RULER_CACHE", {})
    svc = _FakeFolio(["breach of contract", "lease agreement"])
    monkeypatch.setattr(ers.FolioService, "get_instance", classmethod(lambda cls, oid=None: svc))
    return svc


async def test_ruler_patterns_built_once_across_jobs(fake_folio):
    with patch.object(ers.FOLIOEntityRuler, "load_patterns", autospec=True,
                      side_effect=ers.FOLIOEntityRuler.load_patterns) as load:
        first, second = ers.EntityRulerStage(), ers.EntityRulerStage()
        job1 = await first.execute(_job("A breach of contract occurred."))
        job2 = await second.execute(_job("The lease agreement ended."))
    assert load.call_count == 1  # second job reused the cached ruler
    assert first.ruler is second.ruler
    assert [a.span.text for a in job1.result.annotations] == ["breach of contract"]
    assert [a.span.text for a in job2.result.annotations] == ["lease agreement"]
    assert job2.result.annotations[0].concepts[0].branches == ["Area of Law"]


async def test_ruler_cache_rebuilds_after_ontology_reload(fake_folio):
    await ers.EntityRulerStage().execute(_job("A breach of contract occurred."))
    # FolioService._reload swaps in brand-new label dicts.
    fake_folio.labels, fake_folio.multi = _labels("motion to dismiss")
    stage = ers.EntityRulerStage()
    job = await stage.execute(_job("A motion to dismiss and a breach of contract."))
    assert [a.span.text for a in job.result.annotations] == ["motion to dismiss"]


# ── Defect 3: count_active reads headers, not whole job files ──────────────


async def _save(store: JobStore, status: JobStatus, **kw) -> Job:
    job = Job(input=DocumentInput(content="x" * 50_000), **kw)
    job.status = status
    await store.save(job)
    return job


async def test_count_active_does_not_parse_whole_job_files(tmp_path: Path, monkeypatch):
    store = JobStore(base_dir=tmp_path / "jobs")
    for status in (JobStatus.MATCHING, JobStatus.RESOLVING, JobStatus.COMPLETED,
                   JobStatus.FAILED, JobStatus.PENDING):
        await _save(store, status)

    def no_full_parse(*_a, **_k):
        raise AssertionError("count_active parsed a whole job file")

    monkeypatch.setattr(js.json, "loads", no_full_parse)
    assert await store.count_active() == 2


async def test_count_active_tracks_status_changes_and_deletes(tmp_path: Path):
    store = JobStore(base_dir=tmp_path / "jobs")
    job = await _save(store, JobStatus.MATCHING)
    other = await _save(store, JobStatus.ENRICHING)
    assert await store.count_active() == 2
    job.status = JobStatus.COMPLETED
    await store.save(job)
    assert await store.count_active() == 1
    await store.delete(other.id)
    assert await store.count_active() == 0


async def test_count_active_falls_back_for_unexpected_layout(tmp_path: Path):
    store = JobStore(base_dir=tmp_path / "jobs")
    job = Job(input=DocumentInput(content="y" * 5000))
    job.status = JobStatus.MATCHING
    data = json.loads(job.model_dump_json())
    reordered = {"input": data.pop("input"), "result": data.pop("result"), **data}
    (store.base_dir / f"{job.id}.json").write_text(json.dumps(reordered))
    assert await store.count_active() == 1


async def test_count_active_still_fails_stale_jobs(tmp_path: Path):
    store = JobStore(base_dir=tmp_path / "jobs")
    stale = await _save(store, JobStatus.RESOLVING,
                        updated_at=datetime.now(timezone.utc) - timedelta(hours=2))
    assert await store.count_active() == 0
    reloaded = await store.load(stale.id)
    assert reloaded.status == JobStatus.FAILED
    assert reloaded.error == "Job timed out (stale)"


# ── Defect 4: bounded LLM chunk fan-out ────────────────────────────────────


async def test_concept_batch_bounds_concurrent_requests():
    in_flight = peak = 0

    class _LLM:
        async def structured(self, prompt, schema=None, **kw):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            await asyncio.sleep(0.01)
            in_flight -= 1
            return {"concepts": [{"concept_text": "contract", "confidence": 0.9}]}

    chunks = [TextChunk(text=f"chunk {i}", start_offset=i, end_offset=i + 1, chunk_index=i)
              for i in range(60)]
    with patch.object(lci, "build_concept_identification_prompt", return_value="p"):
        out = await lci.LLMConceptIdentifier(_LLM()).identify_concepts_batch(chunks)
    assert peak <= lci.MAX_CONCURRENT_CHUNK_REQUESTS
    assert peak > 1  # still concurrent
    assert len(out) == 60 and all(len(v) == 1 for v in out.values())


# ── Defect 5: semantic ruler skipped when the provider cannot encode ───────


def _index_without_encoder() -> EmbeddingService:
    svc = EmbeddingService(provider=LocalEmbeddingProvider())
    svc._labels = ["breach of contract"]  # loaded from the disk label cache
    svc._metadata = [{"iri": "iri1"}]
    return svc


async def test_semantic_ruler_skipped_without_sentence_transformers(monkeypatch):
    monkeypatch.setattr(embedding_service_mod, "_sentence_transformers_available", lambda: False)
    svc = _index_without_encoder()
    stage = ers.EntityRulerStage(ruler=MagicMock(find_matches=MagicMock(return_value=[])),
                                 embedding_service=svc)
    stage._patterns_loaded = True
    with patch.object(ers, "SemanticEntityRuler") as sem:
        await stage.execute(_job("The contract violation was severe."))
    sem.assert_not_called()

    ruler = SemanticEntityRuler(svc)
    with patch.object(ruler, "_collect_candidates") as collect:
        assert ruler.find_semantic_matches("The contract violation was severe.", set()) == []
    collect.assert_not_called()


def test_can_encode_true_when_local_dependency_present(monkeypatch):
    monkeypatch.setattr(embedding_service_mod, "_sentence_transformers_available", lambda: True)
    assert sr.can_encode(_index_without_encoder())
    assert not sr.can_encode(None)
    assert sr.can_encode(MagicMock())  # remote/test providers are not pre-judged


# ── Defect 6: candidates stay inside sentence/punctuation boundaries ───────


def _phrases(text: str, known=frozenset()) -> set[str]:
    return {p for p, _, _ in SemanticEntityRuler(None)._collect_candidates(text, set(known))}


@pytest.mark.parametrize("text,bad", [
    ("Acme Corp. in the matter", "Corp. in the"),
    ("He sought relief in damages. The court agreed", "in damages. The"),
    ("He sought relief in damages. The court agreed", "damages. The court"),
    ("They signed the lease agreement after the closing", "the lease agreement after"),
    ("United States District Court for the Southern District", "States District Court for"),
    ("The plaintiff, a tenant, sued", "The plaintiff,"),
    ("The plaintiff, a tenant, sued", "plaintiff, a tenant"),
])
def test_prod_neighbor_word_spans_are_not_candidates(text, bad):
    phrases = _phrases(text)
    assert " ".join(bad.split()) not in phrases
    for phrase in phrases:
        words = phrase.lower().split()
        assert words[0] not in sr._SEMANTIC_STOPWORDS
        assert words[-1] not in sr._SEMANTIC_STOPWORDS
        assert not any(w[-1] in ".,;:" for w in phrase.split()[:-1] if "." not in w[:-1])


def test_candidates_keep_the_clean_core_phrases():
    phrases = _phrases("They signed the lease agreement after the closing. "
                       "The U.S. District Court ruled; Acme Corp. appealed.")
    assert {"lease agreement", "signed the lease agreement", "U.S. District Court",
            "District Court ruled", "Acme Corp"} <= phrases


def test_candidates_trim_edge_punctuation_with_correct_offsets():
    text = 'He breached the "confidential information" clause.'
    cands = SemanticEntityRuler(None)._collect_candidates(text, set())
    for phrase, s, e in cands:
        assert text[s:e] == phrase
    assert "confidential information" in {p for p, _, _ in cands}


def test_candidates_do_not_cross_blank_lines():
    assert "Agreement Section" not in _phrases("Lease Agreement\n\nSection 2 rent")
    assert "Confidential Information" in _phrases("Confidential\nInformation clause")


def test_candidate_containing_a_known_span_is_excluded():
    text = "a material contract claim arose"
    s = text.index("contract")
    phrases = _phrases(text, {(s, s + len("contract"))})
    # Strictly contains the known span (starts before it, ends after it).
    assert "material contract claim" not in phrases
    assert not any("contract" in p for p in phrases)
    assert "claim arose" in phrases


# ── Defect 7: forged kids cannot force a JWKS fetch per request ────────────

TEAM = "folio-test.cloudflareaccess.com"
AUD = "annotation-application"


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _forged(signing_key, kid: str) -> str:
    claims = {"aud": [AUD], "iss": f"https://{TEAM}", "exp": int(time.time()) + 300,
              "email": "reviewer@example.com"}
    return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": kid})


def test_unknown_kid_refresh_is_rate_limited(signing_key):
    key = json.loads(RSAAlgorithm.to_jwk(signing_key.public_key()))
    key.update(kid="real", alg="RS256", use="sig")
    calls: list[int] = []

    def fetch():
        calls.append(1)
        return {"keys": [key]}

    verifier = auth.CfAccessVerifier(team_domain=TEAM, aud=AUD,
                                     allowed_emails="reviewer@example.com", jwks_fetcher=fetch)
    for i in range(10):
        with pytest.raises(auth.AccessAuthError):
            verifier.verify(_forged(signing_key, f"forged-{i}"))
    assert len(calls) == 2  # initial fetch + one forced refresh, not 11

    # The real key keeps verifying from the cache.
    assert verifier.verify(_forged(signing_key, "real")) == "reviewer@example.com"
    assert len(calls) == 2

    # Once the interval passes, a new kid may force one more refresh (rotation).
    verifier._last_forced_refresh -= verifier._min_refresh_interval + 1
    with pytest.raises(auth.AccessAuthError):
        verifier.verify(_forged(signing_key, "forged-again"))
    assert len(calls) == 3


# ── Defect 1/2: the shared ruler matches exactly like load_patterns, faster ──

_TRICKY = [
    "breach of contract", "lease agreement", "u.s. district court", "non-compete agreement",
    "deep sea, coastal, and great lakes water transportation", "motion to dismiss",
    "court of appeals", "notice of default", "district court", "contract", "landlord",
    "attorney's fees", "e-discovery", "confidential information", "summary judgment",
]


def test_fast_ruler_and_windows_match_load_patterns_exactly(monkeypatch):
    single, multi = _labels(*_TRICKY)
    old = ers.FOLIOEntityRuler()
    old.load_patterns(single)
    bundle = ers._RulerBundle(
        ruler=ers._build_fast_ruler(single), iri_to_branch={}, iri_to_concept={},
        label_to_concepts={}, labels=single, labels_multi=multi,
        max_label_chars=max(len(k) for k in single),
    )
    monkeypatch.setattr(ers, "_WINDOW_CHARS", 300)  # force many windows
    sentences = [
        "The U.S. District Court denied the motion to dismiss the breach of contract claim.",
        "A non-compete agreement and the lease agreement were breached; attorney's fees followed.",
        "Deep sea, coastal, and great lakes water transportation is regulated by the Court of Appeals.",
        "The landlord sent a notice of default regarding confidential information and e-discovery.",
        "Summary judgment\n\nwas entered by the district court on the contract.",
    ]
    text = " ".join(sentences[i % len(sentences)] for i in range(60))

    def key(ms):
        return sorted((m.start_char, m.end_char, m.entity_id, m.match_type, m.text) for m in ms)

    expected = key(old.find_matches(text))
    assert len(expected) > 100
    assert key(bundle.find_matches(text)) == expected
