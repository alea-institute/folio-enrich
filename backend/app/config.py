from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "FOLIO Enrich"
    debug: bool = False

    # Job storage
    jobs_dir: Path = Path(os.path.expanduser("~/.folio-enrich/jobs"))

    # Feedback storage
    feedback_dir: Path = Path(os.path.expanduser("~/.folio-enrich/feedback"))

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["*"]

    # Chunking
    max_chunk_chars: int = 3000
    chunk_overlap_chars: int = 200

    # LLM — global defaults (used when per-task overrides are not set)
    llm_provider: str = "google"
    # Empty = use the provider's own default model, so an env that pins only
    # FOLIO_ENRICH_LLM_PROVIDER still resolves a valid model. For the default
    # provider (google) this resolves to gemini-3-flash-preview (Gemini 3 Flash).
    llm_model: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    mistral_api_key: str = ""
    cohere_api_key: str = ""
    meta_llama_api_key: str = ""
    groq_api_key: str = ""
    xai_api_key: str = ""
    github_models_api_key: str = ""

    # Bring-your-own-key enforcement. When True, the server-stored API keys are
    # NEVER used to serve enrichment requests — every request must supply its own
    # key. Set this on public deployments (e.g. PROD) so anonymous visitors can't
    # spend the operator's key. Leave False for self-hosted/trusted instances
    # where a shared server key is intended. See backend/app/api/routes/settings.py
    # (_get_api_key_for_provider) for where the fallback is gated.
    require_user_api_key: bool = False

    # Per-task LLM overrides (empty = use global llm_provider/llm_model)
    llm_classifier_provider: str = ""
    llm_classifier_model: str = ""
    llm_extractor_provider: str = ""
    llm_extractor_model: str = ""
    llm_concept_provider: str = ""
    llm_concept_model: str = ""
    llm_branch_judge_provider: str = ""
    llm_branch_judge_model: str = ""
    llm_area_of_law_provider: str = ""
    llm_area_of_law_model: str = ""
    llm_synthetic_provider: str = ""
    llm_synthetic_model: str = ""
    llm_document_type_provider: str = ""
    llm_document_type_model: str = ""

    # Ollama auto-management
    ollama_auto_manage: bool = True
    ollama_base_url: str = "http://localhost:11434"
    lmstudio_base_url: str = "http://localhost:1234"
    custom_base_url: str = "http://localhost:8080"
    llamafile_base_url: str = "http://localhost:8080"
    ollama_model_simple: str = "qwen3:4b"     # ~2.5GB — classification, area_of_law
    ollama_model_medium: str = "qwen3:8b"     # ~5GB — concept, branch_judge, synthetic
    ollama_model_complex: str = "qwen3:14b"   # ~9GB — metadata extraction, individual, property

    # Embedding
    embedding_provider: str = "local"  # local, ollama, openai
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_disabled: bool = False
    semantic_similarity_threshold: float = 0.80

    # Contextual reranking — disabled by default (2026-02-27).
    # The 50/50 LLM-context / pipeline-score blend was degrading precision
    # and recall in testing: the LLM context scores often inflated marginal
    # matches and diluted high-confidence pipeline signals, producing noisier
    # annotations overall.  Re-enable only after validating that blended
    # scores improve F1 on a representative evaluation set.
    contextual_rerank_enabled: bool = False

    # Individual extraction
    individual_extraction_enabled: bool = True
    individual_regex_only: bool = False  # Skip LLM, only library/regex extractors
    llm_individual_provider: str = ""
    llm_individual_model: str = ""

    # Property extraction
    property_extraction_enabled: bool = True
    property_regex_only: bool = False  # Skip LLM, only Aho-Corasick matching
    llm_property_provider: str = ""
    llm_property_model: str = ""

    # FOLIO OWL auto-update
    folio_auto_update: bool = True
    folio_update_check_interval_hours: int = 24

    # Multi-ontology (see docs/plans/2026-07-01-002-feat-multi-ontology-...).
    # FOLIO is the default ontology; the Catholic Semantic Canon is now also
    # selectable via ?ontology=canon. Request threading resolves/judges/extracts
    # against the job's ontology everywhere, and per-ontology embedding gating
    # ensures a Canon job never scores against FOLIO's vectors (PR #14). On the
    # first Canon request the OWL lazy-loads via the hardened ingestion path
    # (~14 MB download + validate, one-time).
    default_ontology: str = "folio"
    enabled_ontologies: list[str] = ["folio", "canon"]
    # Defensive ceiling on how many NON-default ontologies stay resident (their
    # FolioService + embedding index cached in memory). When exceeded, the least-
    # recently-used non-default ontology is evicted; the default is never evicted.
    # Default (3) comfortably keeps folio + canon resident, so eviction never fires
    # in practice — it just bounds memory if many ontologies are ever added.
    max_resident_ontologies: int = 3

    # Admin token gating the mutating OWL-update routes (check/apply/rollback),
    # which trigger network fetches + runtime hot-reloads. When set, those routes
    # require a matching X-Admin-Token header; when empty (local/trusted), they are
    # unauthenticated. Set on public deployments. Mirrors require_user_api_key.
    admin_token: str = ""

    # Translation matching — index FOLIO translations for text matching
    translation_matching_enabled: bool = False

    # Triple extraction & POS tagging
    triple_extraction_enabled: bool = True
    pos_tagging_enabled: bool = True

    # POS confidence modulation
    pos_confidence_enabled: bool = True           # Master switch for all POS adjustments
    pos_concept_mismatch_penalty: float = 0.15    # Penalty when concept span POS != expected
    pos_property_mismatch_penalty: float = 0.12   # Penalty when property span POS mismatches
    pos_branch_affinity_boost: float = 0.05       # Boost/penalty for POS-branch alignment

    # Candidates
    max_candidates: int = 5
    # Skip the (expensive) backup/runner-up multi-strategy search for concepts that
    # already resolved to a definitive exact FOLIO IRI. Their "alternatives" are just
    # other labels sharing a word (measured noisy) and this search is the dominant
    # resolution cost. Backups are still computed for genuinely ambiguous concepts
    # (those resolved via fuzzy search, i.e. no exact IRI).
    skip_backups_for_exact_matches: bool = True
    # Semantic-relevance filtering of backup (runner-up) candidates. The raw search
    # score cannot separate signal from noise (a substring match like "Non-Human
    # Authorship" for "Non" scores as high as a real match), so after resolution we
    # score each backup's definition/label against the mention's sentence context via
    # the EmbeddingService and drop those below the threshold. No-op when embeddings
    # are unavailable (e.g. DEV/Railway) — backups pass through unchanged.
    backup_semantic_filter_enabled: bool = True
    backup_semantic_relevance_threshold: float = 0.45  # TUNE against captured sims
    # Structural branch-coherence bonus: a backup sharing a FOLIO branch with the
    # primary is far more likely a genuine alternative sense (e.g. "Court" primary in
    # "Forums and Venues" → "Court Forum" same branch = real; "Court Costs" in
    # "Objectives" = word-collision noise). The embedding score alone can't see this.
    # Added to the backup's similarity ONLY for the keep/drop decision (displayed
    # confidence stays the honest raw similarity). Because it is additive to the
    # residual sim, a modest bonus rescues the good same-branch outlier without
    # re-admitting lower-sim same-branch noise. Set 0.0 to disable. TUNE on PROD.
    backup_branch_coherence_bonus: float = 0.12

    # Job management
    job_retention_days: int = 30
    max_concurrent_jobs: int = 10
    stale_job_timeout_minutes: int = 30

    # Rate limiting
    rate_limit_requests: int = 200
    rate_limit_window: int = 60

    # File size limit (bytes)
    max_upload_size: int = 50 * 1024 * 1024  # 50MB

    model_config = {"env_prefix": "FOLIO_ENRICH_"}


settings = Settings()
