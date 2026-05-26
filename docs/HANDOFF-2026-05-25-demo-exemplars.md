# CE Handoff — Pre-Baked Exemplar Demo Mode (2026-05-25)

Session handoff for the next Compound Engineering session. Everything below is **shipped
to DEV + PROD and verified** unless marked otherwise.

## TL;DR
Built **"Try an Exemplar" demo mode**: a session-scoped Demo toggle that puts `DEMO` badges
on all 22 exemplar buttons and loads pre-baked, full-LLM-enriched results **instantly — no API
key, no tokens, no wait**. Generated once with Gemini 3 Flash, served as static JSON. Plus a
content-based freshness check, PROD local embeddings, and a normalization-stage bug fix.

- **Origin docs:** `docs/brainstorms/2026-05-25-demo-exemplars-refresh-brainstorm.md` → `docs/plans/2026-05-25-002-feat-prebaked-exemplar-demo-mode-plan.md` (status: completed).
- **Live:** PROD `https://enrich.openlegalstandard.org` · DEV `https://folio-enrich-production.up.railway.app`
- **Branches/commits:** `dev` = `main` = PROD = `75c3faa`. Feature commits: `70328c5`, `0a96db4`, `490b1d1`, `7d93e97`, `437a5e6`, `847ebd3`, `a893c60`, `6516d19`, then Railway-embeddings experiment + revert (`48b73ab`→`6b58898`), then `75c3faa` (normalization fix).

## What shipped

1. **Demo mode UI** (`frontend/index.html`): `aria-pressed` Demo toggle, CSS `.demo-mode #demoExemplars .sample-btn::after` DEMO badge, click → fetch `/static/demos/<slug>.json` → `hydrateFromDemo()` → push `?demo=<slug>`. Soft lockdown (editing/Enrich exits to a live run), `popstate` back/forward, missing-JSON toast fallback, `aria-live` announcements, `.sr-only` utility. Old `DEMO_CATALOG`/`openDemos`/`#demoLinksModal`/header buttons retired.
2. **22 baked demos** (`frontend/demos/*.json`, ~82MB): 7 Rich Enrichment + 15 Quick Start, full LLM output (up to 498 annotations / 102 individuals / 98 properties / 90 triples). Lean+compact (top-level annotations/etc. dropped — they live in `cache.job.result`; `hydrateFromDemo` derives them).
3. **Single source of truth**: the 22 exemplar texts come from the inline `SAMPLES` object in `index.html` (lines ~4086–4160). `backend/scripts/extract_exemplars.py` extracts them via **Node** (template literals); `demo_documents.py` exposes 22-slug meta + `load_demo_documents()`. Drift guard: `tests/test_samples_source.py`.
4. **Generator** (`backend/scripts/generate_demos.py`): full LLM pipeline (default Gemini 3 Flash), `--provider/--model/--only/--no-llm`, compact lean payload. **Regenerate:** `cd backend && FOLIO_ENRICH_GOOGLE_API_KEY="$GOOGLE_API_KEY" .venv/bin/python scripts/generate_demos.py` (~60–90 min for 22).
5. **Exports in demo mode** (`backend/app/services/demo_seed.py`): startup seeds each demo's `cache.job` into the job store (`PROTECTED_JOB_IDS` shields them from cleanup) so all 13 export formats resolve. Tests: `tests/test_demo_seed.py`.
6. **Content-based freshness check**: `.owl-version` / `.samples-version` / `.pipeline-version` sidecars in `frontend/demos/`, compared by hash (replaced fragile mtime which app-startup + git ops bumped). `--check` gated behind the `demo_regen` pytest marker.
7. **PROD local embeddings**: `sentence-transformers` installed in PROD's **uv** venv; embedding cache (`~/.folio-enrich/cache/embeddings/`, keyed by OWL hash) seeded from local to avoid a startup outage. Declared as a pyproject `[embeddings]` extra.
8. **Bug fixes:** Gemini structured-JSON trailing-data parse (`google_provider._loads_first_json`); normalization stage `n_sentences` (read `canonical.sentences` which doesn't exist → now sums `c.sentences` across chunks).

## Hard-won gotchas (don't relearn these)
- **PROD venv is uv-managed — NO `pip`.** Use `cd backend && ~/.local/bin/uv pip install --python .venv/bin/python <pkg>`. (The deploy memory's old `.venv/bin/pip install` is wrong.)
- **DEV (Railway) cannot build embeddings at startup.** The all-MiniLM index build is ~2138 batches ≈ **~50 min** on Railway's CPU → blows past the healthcheck window → crash loop. A volume doesn't help (build never finishes to write the cache). DEV intentionally runs with embeddings **disabled** (graceful degradation). The `[embeddings]` extra is NOT installed in the Dockerfile. PROD (bare-metal) gets embeddings via a pre-seeded cache. See `~/.claude/.../memory/reference_railway_dev.md`.
- **Keep `llm_model` empty** in config so env-pinned providers resolve their default model.
- **Demo files are committed to git** (~82MB) — established pattern; regenerate + recommit on ontology/pipeline changes.
- **`extract_exemplars.py` needs Node** (generation/tests only — NOT app runtime; the app never imports it, so PROD/Docker don't need Node).

## Open items
- **Two detached orphan volumes remain** (`folio-enrich-volume` id `84e73acc…` + `folio-enrich-volume-VzhL` id `d6767a38…`, both `service=None`, ~150MB each — **harmless, just clutter**). The Railway **CLI `volume delete` is non-functional here**: it prints `Volume "…" deleted` and exits 0 but the volume persists in `railway volume list` (same id). Likely 2FA-gated — `volume delete --help` lists `--2fa-code` "required if 2FA is enabled in non-interactive mode"; without it the delete is silently rejected. To actually delete: either the **Railway dashboard** (click the detached volume node → delete; safe now they're detached, won't trigger a service redeploy), or **`railway volume delete --volume <name> --2fa-code <code> --yes`** if 2FA is on. (Update 2026-05-25.)

### ⚠️ DEV must stay volume-less — attaching ANY volume crashes it (learned the hard way 2026-05-25)
- **What works / doesn't on volumes:** CLI `volume delete` = no-op (see above). CLI `volume detach` + `railway redeploy --service folio-enrich --yes` = **works** and is how you recover. DEV came back `200` ~30s after redeploy.
- **Why a volume kills DEV:** Railway mounts fresh volumes as **root**, app runs as **`appuser`**. The `gosu` chown entrypoint that fixed this was removed in revert `6b58898`. So a volume at `/home/appuser/.folio-enrich` → `JobStore()` `mkdir` → `PermissionError: [Errno 13] … /home/appuser/.folio-enrich/jobs` → crash loop → 502.
- **Railway dashboard gotcha:** a staged "Edited / 1 Change" on the service card can be an *add-volume* op, not a delete. Deploying it **adds & mounts** a volume → outage. Read the staged change carefully before clicking Deploy; for volume cleanup, act on the **volume node** itself, not the service.
- **DEV local embeddings (deferred by decision):** if ever wanted, host the prebuilt `.pkl` (R2/GitHub release) + download at startup, or pre-seed a volume from it. Not worth it for a keyless test env; PROD has embeddings.
- **Standalone executables** (GitHub Actions PyInstaller, `.github/workflows/build.yml`) run without local embeddings by design (torch would bloat the binary) — graceful degradation, no regression.

## Deployment quick-ref
- **DEV:** push to `dev` → Railway auto-deploys (Dockerfile build; no embeddings).
- **PROD:** `git checkout main && git merge dev && git push origin main`, then `ssh -i "<key>" ubuntu@54.224.195.12 'cd /home/ubuntu/folio-enrich && git pull origin main'`, restart only if `app/` changed: `sudo -n systemctl restart folio-enrich`. Embeddings load from the seeded cache (~25s). See `reference_prod_server.md` for SSH/paths.

## Verify (PROD)
1. https://enrich.openlegalstandard.org → click **Demo** → badges on 22 exemplars.
2. Click **Complaint** → instant render (369 annotations / 82 triples), DevTools shows **zero `/enrich` POST**.
3. Export (e.g. RDF/Turtle, Neo4j CSV) → downloads.
4. Type in the box → exits demo cleanly.
