# FOLIO Insights on the demo memo (2026-11-25)

**What ran.** `folio-insights` 0.1.0 (folio-insights checkout at `269171e`, its own `.venv`)
extracted propositions ("knowledge units") from the synthetic demo memo
(`demo-document.md`, first HTML-comment line stripped, saved as `distribution-memo.md`), then
`folio-insights serve` showed them in the review viewer. Output, review database and corpus
root all lived in a scratch directory; the repo's tracked files were not touched.

**Provider and cost.** Local Ollama, model `llama3.1:8b` (CPU only, no GPU), for every LLM
task. No API key. **Cost US$0.00** (the CLI's spend cap was set to $0.01 because it refuses 0;
Ollama calls are unpriced). Not the README default (`gemini-2.5-flash-lite`): a free route was
required.

## Commands

```sh
export FOLIO_INSIGHTS_FOLIO_ENRICH_PATH=<folio-enrich checkout>/backend   # ingestion bridge
export FOLIO_INSIGHTS_FOLIO_MAPPER_PATH=<folio-mapper checkout>/backend
export FOLIO_INSIGHTS_LLM_TIMEOUT=900                      # CPU Ollama needs more than the 120 s default
export FOLIO_INSIGHTS_LLM_MAX_UNIT_FAILURE_RATIO=0.5       # default 0.05; see "Honest limits"
export FOLIO_INSIGHTS_TAGGER_MAX_UNIT_FAILURE_RATIO=0.5
box-run --max 8G -- folio-insights extract ./src --corpus distribution-memo --output ./output \
  --llm-provider ollama --llm-model llama3.1:8b --max-spend-usd 0.01
# viewer: run from the scratch dir so ./output resolves; PYTHONPATH makes the repo's api/ importable
PYTHONPATH=<folio-insights checkout> FOLIO_INSIGHTS_CORPUS_ROOT=./corpora-root \
  folio-insights serve --port 8812
```

The viewer lists a corpus only when `output/<corpus>/corpus-meta.json` exists (the upload
flow writes it; the CLI does not). One was written by hand:
`{"id":"distribution-memo","name":"Distribution Memo (synthetic)","created_at":"2026-11-25T14:13:00Z"}`.

**Run history (all resumed from checkpoints, same output dir):**

1. 07:29: refused, `spend cap must be a finite, positive number of USD` (`--max-spend-usd 0`).
2. 07:29: refused, ingestion bridge could not find folio-enrich (fixed with the env var above).
3. 07:30–07:42: ingestion, structure, boundary detection (19 units), distiller (190 s); then
   `knowledge_classifier: the classify LLM call failed on 7 of 19 units (36.8% > 5.0% allowed)`,
   mostly `ollama request timed out` at the 120 s default.
4. 07:42–08:12: classifier (1,335 s), FOLIO tagger (404 s, `19/19 units tagged`); the box's
   memory-pressure guard then shed the job (`box-run: exit 143`) before output.
5. 08:12: dedup and output, `Pipeline complete for 'distribution-memo': 19 units in 6.7s`.

Output: `extraction.json`, `review.json`, `proposed_classes.json`; 19 units (viewer: High 9,
Medium 10, Low 0).

## Propositions for a slide card (verbatim)

Tags: FOLIO label | branch | IRI | tag confidence | extraction path. `proposed_class` tags have
no FOLIO IRI: the tagger found no concept and proposed one.

**1. "Wrongful termination claim requires notice period and no exclusivity clause."**
(principle, confidence 0.905; source: "Wrongful termination without cause: notice period; exclusivity clause.")
- Wrongful termination | Objectives | `RDJYLQ3woaBs6FkT7wMbB4U` | 0.81 | entity_ruler
- exclusivity clause | Objectives | `RDgEiiX23zftUP0Mggfc68n` | 0.91 | entity_ruler
- claim | Objectives | `R9Bt6YyjZVGU1dHNZZMG1Ue` | 0.72 | entity_ruler
- notice | Document / Artifact | `RB3FT9lFNQIjRnFIueLgCa7` | 0.72 | entity_ruler
- no exclusivity clause | Objectives | `R9BhvOfuZgSGUlQfxwSi4b5` | 0.72 | entity_ruler
- Notice Period | (proposed class) | 0.7

**2. "Limitation of liability clauses can limit or exclude direct and consequential damages, including lost profits and prejudgment interest."**
(principle, 0.9; source: "Damages: direct damages, consequential damages, lost profits, prejudgment interest; limitation of liability clause.")
- consequential damages | Objectives | `RouKBMqFNMZxi21EPh6JJ6` | 0.73 | entity_ruler
- damages | Objectives | `RCCv5YLoHUOm5AlqcCBzqGf` | 0.72 | entity_ruler
- Limitation of Liability | Objectives | `RBukB9MGGdY4Kwx3b6itiwi` | 0.8 | llm
- Prejudgment Interest | Objectives | `RObDXKmoefrAqYpuco45fm` | 0.5 | llm
- Direct Damages, Lost Profits | (proposed classes) | 0.7, 0.9

**3. "Arbitral tribunal can grant interim relief for trademark infringement and unfair competition."**
(principle, 0.81; source: "Interim relief: arbitral tribunal; emergency arbitrator; trademark infringement; unfair competition.")
- trademark infringement | Objectives | `RBQCFqSF0Q0sCqCcEwv2pgz` | 0.81 | entity_ruler
- Unfair Competition | Objectives | `R8viNe7dpcLA9kGH5gl7YE6` | 0.7 | llm
- grant | Event | `RaQIRktfYrGWDS7HAq0N6f` | 0.72 | entity_ruler

**4. "Nonconforming goods under Article 25 CISG constitute a fundamental breach of contract."**
(principle, 0.9; source: "Fundamental breach of contract: nonconforming goods, Article 25 CISG.")
- breach of contract | Objectives | `RC2fjcpsEbrVvVymvt4oASx` | 0.72 | entity_ruler
- goods | Asset Type | `RDS8DPtuFReTFfJ5nGCczD5` | 0.72 | entity_ruler
- contract | Document / Artifact | `R88D8i8AcSTUig2X3yPbFHg` | 0.72 | entity_ruler
- Article | Document / Artifact | `RCLzAnLlcCjfFg827Yywk1I` | 0.72 | entity_ruler
- Nonconforming goods, Article 25 CISG, Fundamental breach of contract | (proposed classes) | 0.8, 0.9, 0.7

**5. "Supplier's termination of agreement without notice and granting trademark license to competitor is potentially invalid."**
(principle, 0.8)
- Contract Termination | Event | `RB3TXlxV89oDiy7HtSN9cF0` | 0.8 | llm
- Supplier | Actor / Player | `R7kkf8NvitG8hubZUnTwevG` | 0.72 | entity_ruler
- license | Objectives | `RKKRGOkIme6pnG2BSePt1Z` | 0.72 | entity_ruler
- Trademark License | (proposed class) | 0.7

All IRIs are under `https://folio.openlegalstandard.org/`.

**Tie-in with ontology-dynamic.** FOLIO Insights tags proposition 1 with
`RDJYLQ3woaBs6FkT7wMbB4U`, whose FOLIO label is **Wrongful Discharge or Termination**, an
employment claim (the viewer shows the matched text "Wrongful termination"). The memo's claim
is commercial. ontology-dynamic, run on the same memo, proposed exactly the missing concept,
"Wrongful Termination of Commercial Contract" (see `ontology-dynamic.md`).

## Clip and still

- **`media/insights.mp4`:** 21.6 s, 1920×1080, H.264 CRF 28, 0.68 MB. Script
  `capture/insights.mjs` (dark theme); trimmed `-ss 0.5`. Sequence: Review tab, corpus
  "Distribution Memo (synthetic)", All Units (19) with the extracted propositions → scroll the
  list → expand FOLIO branch **Objectives** → concept **Wrongful termination**
  (IRI `RDJYLQ3woaBs6FkT7wMbB4U`): "Wrongful termination claim requires notice period and no
  exclusivity clause." and "Timely notice defeats waiver defense in wrongful termination
  cases." → select the first; Source Context highlights its memo line → **Limitation of
  Liability**: proposition 2 → **Unfair Competition**: proposition 3. Read-only: no approve,
  reject or edit.
- **`media/insights-still.jpg`:** Wrongful termination concept with proposition 1 selected
  and its source line highlighted (2× scale, downscaled to 1920 wide).
- **Screening:** 11 frames (1 per 2 s) plus the still inspected; only synthetic party names,
  FOLIO labels and IRIs, and a relative source path; no keys, tokens, emails or personal data.

## Honest limits

- **Small local model.** llama3.1:8b on CPU, not the default Gemini model. Some units are
  weak or wrong: "Distill core insight from legal advocacy text" and "Distill mediation
  settlement agreement for release and indemnification" echo the prompt, not the memo.
  Choose card examples from the five above.
- **Failure tolerance raised.** The per-stage LLM failure tolerance was raised from 5% to 50%
  so the CPU run could finish; failed classify or novelty calls keep defaults (type ADVICE,
  novelty 0). A hosted model would not need this.
- **Badges, not labels.** The unit cards show tag *sources* (EntityRuler, LLM,
  proposed_class); concept labels appear in the left FOLIO tree, which the clip uses.
- **Highlight offset.** The Source Context highlight sits a few characters early on some
  units (visible in the still).
