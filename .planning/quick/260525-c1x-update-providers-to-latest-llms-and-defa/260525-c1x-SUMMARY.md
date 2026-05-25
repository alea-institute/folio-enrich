---
quick_id: 260525-c1x
title: Update providers to latest LLMs and default to Gemini 3 Flash
date: 2026-05-25
status: complete
---

# Quick Task 260525-c1x — Summary

## What changed
1. **Latest models added** to `backend/app/services/llm/registry.py` `KNOWN_MODELS`:
   - OpenAI → `gpt-5.5` (GPT-5.5)
   - Anthropic → `claude-opus-4-7` (Claude Opus 4.7) — also added to `_FALLBACK_MODELS` in `anthropic_provider.py`
   - Google → `gemini-3.1-flash-lite` (Gemini 3.1 Flash Lite), `gemini-3.5-flash` (Gemini 3.5 Flash)
2. **Gemini 3 Flash is now the default LLM, top of the list:**
   - `config.py`: `llm_provider="google"` (was `ollama`); `llm_model` kept **empty** (was also empty) so it
     resolves to the provider's own default — for google that is `gemini-3-flash-preview`. (Hardcoding the
     google model id was reverted: it would break a deployment whose `.env` pins only the *provider* —
     e.g. PROD pins `FOLIO_ENRICH_LLM_PROVIDER=anthropic`, which with a hardcoded google model id would
     call Anthropic with an invalid model. Empty → Anthropic resolves `claude-sonnet-4-6` correctly.)
   - `KNOWN_MODELS[google]` reordered so **Gemini 3 Flash is first**.
   - `settings.py` `list_providers` now emits the configured default provider first → **Google Gemini heads the provider dropdown**.

## Verified
- `GET /settings/providers` → `current = {google, gemini-3-flash-preview}`; provider order `google, openai, anthropic, …`
- `GET /settings/known-models` → `google[0] = gemini-3-flash-preview`; anthropic ends `claude-opus-4-7`; openai ends `gpt-5.5`
- Frontend dropdowns: provider = **Google** (selected, first), model = **Gemini 3 Flash** (selected, first)
- Backend test suite: **674 passed** (updated `test_task_llms.py::test_env_override` — the per-task-isolation test that pinned the old `ollama` default; now uses an `openai` override against the `google` global default)

## Flags / follow-ups
- **Default flip Ollama → Google requires a Google API key** (`FOLIO_ENRICH_GOOGLE_API_KEY`). Without one,
  the LLM chip shows "Not Configured" and enrichment falls back to the symbolic-only banner (graceful).
  Set the key on Railway DEV / PROD to make Gemini the live default there.
- **Model IDs newer than training** — `gpt-5.5`, `gemini-3.5-flash`, `gemini-3.1-flash-lite` were taken from
  May-2026 web results using standard naming; worth a quick verify vs provider docs. The app's live
  model-refresh (with a key) supersedes these static fallback entries anyway.
- **`ollama_auto_manage` left `True`** (no-ops where Ollama isn't installed); flip to `False` if you want
  to stop auto-starting local Ollama now that the default is cloud.
