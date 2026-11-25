# ALEA Intake capture — evidence (2026-11-25)

## Outputs

- `media/intake.mp4`: 24.2 s, 1920x1080, H.264 CRF 28, no audio, 570 KB.
- `media/intake-still.jpg`: 2560x1440 (deviceScaleFactor 2), JPEG q85. Shows the "Issues and FOLIO concepts" list.
- Script: `capture/intake.mjs` (Playwright; viewport 1280x720 at DSF 2, video cropped from the 1920x1080 canvas and scaled to 1920x1080).

## How it ran

- **DEV not used.** The gate credential exists, but the DEV showcase requires each visitor to bring a paid
  OpenAI, Anthropic, or Google key, and this capture used no paid key.
- **Local run.** ALEA Intake (alea-intake branch `feat/2026-11-08-0337-feat-public-showcase-launch-plan-pr1`,
  commit `6c2de95`). The backend ran from the repo venv in showcase mode with SQLite in a scratch directory.
  The frontend ran on the Vite dev server with `VITE_SHOWCASE_MODE=true`. Neither touched the repo's files.
- **LLM.** Local Ollama `llama3.1:8b` on CPU. A launcher shim pointed alea-llm-client's OpenAI-compatible
  client at the Ollama endpoint, and a placeholder string satisfied the key format check.
  **Cost: $0.**
- **Embeddings and ontology.** Intake's local sentence-transformers embeddings and its cached FOLIO OWL.
- **Analysis timing.** One real analysis run, intake 1, ran 13:12–13:28 UTC and converged after a single
  showcase iteration (issue_spot, explore, research, fact_map, gap_analyze, question_gen). Deadline detection
  and safety screening finished at 13:30. The court self-help memo step was still running at the 40-minute
  capture timeout because another local job was sharing Ollama, so the first recording never reached the
  results view.
- **Second pass replays that run (disclosed).** `REPLAY_TOKEN_FILE` mode drives the same real UI and
  types the story visibly. It stubs only the session setup calls (guest token, consent, intake create,
  WebSocket story delivery) to point at intake 1, and it stubs the memo call with an empty result.
  Run 1's real backend serves the status, the results, and the visualization. The issues on screen are
  that run's actual output. The clip neither opens the memo tab nor shows a memo.
- **Edited time.** The progress spinner shows for about 3.5 s in the clip, but the real analysis took
  about 16 minutes on CPU.

## Input (typed on camera)

> I run a small wine import business in São Paulo. Our Chilean supplier sent wine that failed Brazilian customs testing, so the government made us recall it and fined us. Then the supplier ended our exclusive contract without warning and started selling through a competitor in Rio, still using the brand we were promoting. What can I do?

## Issues returned (verbatim; run status `converged`)

| Issue | FOLIO IRI | Jurisdiction | Confidence |
|---|---|---|---|
| Breach of Contract | https://folio.openlegalstandard.org/RC2fjcpsEbrVvVymvt4oASx | Brazilian law | 1.0 |
| Unfair Competition | (none resolved) | Brazilian law | 0.4 |
| Trademark Infringement | https://folio.openlegalstandard.org/RBQCFqSF0Q0sCqCcEwv2pgz | Brazilian law | 0.9 |
| Deceptive Trade Practices | (none resolved) | Brazilian law | 0.4 |
| Anti-Trust Violation | https://folio.openlegalstandard.org/RDsDXHKUsZoJfz87jnz7zjj | Brazilian law | 0.7 |
| Customs-Import Violation | (none resolved) | Brazilian law | 0.4 |
| Breach of Distributorship Agreement | (none resolved) | — | 0.4 |
| Misrepresentation | (none resolved) | — | 0.2 |

- **On screen.** The clip shows all 8 issue headings, plus FOLIO concept chips for the 3 resolved issues:
  Breach of Contract, Trademark Infringement, and Anti-Trust Violation.
- **Narrative view.** The story text appears highlighted, with a legend that color-codes the 8 issues.
- **Gaps, questions, and deadlines.** The run also produced 27 gaps, 9 follow-up questions, and 3 deadlines,
  none of them shown in the clip.
- **Model quality.** These issues come from an 8B local model and do not reflect output from the reference model.

## Screening

- **Method.** Extracted one frame every 2 s from the final mp4 (12 frames) and inspected each one, plus the still.
- **Result: clean.** No API keys or tokens, no email addresses, no personal data, and no sign-in screen.
  The placeholder key field stays off-frame, and the browser URL bar never appears (headless page capture).
  The screening frames have been deleted.

## Cleanup

- **Stopped.** The local backend (uvicorn under box-run) and the Vite dev server.
- **Deleted.** The scratch SQLite DB, the minted guest token, the local copy of the DEV preview passphrase,
  the raw webm files, and the screening frames.
- **Never started.** Docker containers. The capture also left the shared Ollama daemon alone.
