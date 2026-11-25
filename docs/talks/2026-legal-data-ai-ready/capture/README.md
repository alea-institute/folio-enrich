# Capture scripts

Each `*.mjs` here records one deck clip with Playwright and writes into `../media/`
(git-ignored). Run them from the deck folder (`docs/talks/2026-legal-data-ai-ready/`).

## Prerequisites

- **Playwright.** The scripts `require('playwright')`. If Node cannot resolve it, point
  `NODE_PATH` at any `node_modules` that holds Playwright 1.6x, for example
  `NODE_PATH=<dir>/node_modules`, where `find ~/.npm/_npx -maxdepth 3 -name playwright`
  lists candidates (2026-11-25 shoot used the Playwright 1.65.0 copy).
- **ffmpeg** at `/usr/bin/ffmpeg`.

## Clip `mapper` (FOLIO Mapper)

```bash
node capture/mapper.mjs        # -> media/mapper-raw.webm, media/mapper-still.jpg, media/mapper-run.json
ffmpeg -y -ss 1.1 -i media/mapper-raw.webm -an -c:v libx264 -pix_fmt yuv420p -crf 28 \
  -preset slow -movflags +faststart -vf scale=1920:1080 media/mapper.mp4
```

- Picks **No LLM** (local fuzzy matching; no key ever entered), types a 16-label
  **synthetic** taxonomy, parses it, chooses **Continue Anyway** on the no-LLM warning,
  then for the first three labels opens and accepts the highest-scoring candidate.
- The first three labels sit first on purpose: they score 85, 99 and 98 on the live
  app (2026-11-25). If scores drift, check `accepted` in `media/mapper-run.json`.
- `-ss` trims the blank lead-in; set it a little below `videoMarks.ready` in the run JSON.

## Clip `ontokit` (OntoKit)

```bash
node capture/ontokit.mjs       # ONTOKIT_URL=https://ontokit.dev.openlegalstandard.org to use DEV
ffmpeg -y -ss 1.1 -i media/ontokit-raw.webm -an -c:v libx264 -pix_fmt yuv420p -crf 28 \
  -preset slow -movflags +faststart -vf scale=1920:1080 media/ontokit.mp4
```

- Anonymous and read-only: projects list, FOLIO project, then
  Area of Law > Intellectual Property Law > Trademark and Trade Dress Law.
- No sign-in. To add the suggest/review flow later, sign in in a separate,
  **unrecorded** context, save `storageState`, and pass it to the recording context, so the
  sign-in screen never appears on camera.

## Screening (mandatory after every re-shoot)

```bash
mkdir -p ~/screen && ffmpeg -i media/<id>.mp4 -vf fps=0.5 ~/screen/f%02d.jpg
```

Look at every frame for keys, tokens, email addresses, real people's names or personal
data; re-shoot if any appear; then `rm -rf ~/screen`. Keep each MP4 at or under 20 MB.

## Clips `enrich-tag`, `enrich-panels` and still `demo-doc` (FOLIO Enrich)

Shows the pre-computed result in `evidence/enrich-result.json` (demo format, `{demo, cache}`)
for `demo-document.md`. No LLM and no key: the app renders a baked result.

```bash
# 1. Local FOLIO Enrich (from the repo root); serves the frontend at /
(cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8731) &
# 2. Capture (from the deck folder)
node capture/enrich-tag.mjs     # -> media/enrich-tag-raw.webm, enrich-tag-still.png, demo-doc-still.png
node capture/enrich-panels.mjs  # -> media/enrich-panels-raw.webm, enrich-panels-still.png
for c in enrich-tag enrich-panels; do
  ffmpeg -y -ss 1.0 -i media/$c-raw.webm -an -c:v libx264 -pix_fmt yuv420p -crf 28 \
    -preset slow -movflags +faststart -vf scale=1920:1080 media/$c.mp4; done
for s in enrich-tag-still demo-doc-still enrich-panels-still; do
  ffmpeg -y -i media/$s.png -vf scale=1920:-2 -q:v 3 media/$s.jpg && rm media/$s.png; done
# 3. Stop the backend you started.
```

- **Loading.** `enrich-common.mjs` opens `/?demo=talk_distribution_breach`, the same
  deep-link path "Try an Exemplar" uses, and Playwright answers
  `/static/demos/talk_distribution_breach.json` from `evidence/enrich-result.json`.
  Nothing is copied into `frontend/demos/`. It also answers the per-tag lineage endpoint
  from the same JSON, because the backend seeds jobs only for files in `frontend/demos/`.
- **Pointer.** Playwright video draws no cursor, so the scripts inject a small blue dot.
- **enrich-tag.** Tags on load, a slow scroll, then clicks `ICC` (individual: International
  Chamber of Commerce), `breach of contract` and `trademark infringement`; each click opens
  the tooltip and the detail panel (FOLIO hierarchy, IRI, translations, pipeline lineage).
- **enrich-panels.** Concepts (Objectives branch expanded), Individuals, Properties, Triples.
- **demo-doc still** crops to the results pane, so it is 1920 wide but not 16:9.
- Screen every re-shoot as described under "Screening".
