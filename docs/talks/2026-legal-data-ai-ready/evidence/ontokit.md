# Evidence: OntoKit clip

- **URL:** https://ontokit.openlegalstandard.org (PROD; the DEV fallback was not needed)
- **Date:** 2026-11-25
- **Sign-in:** none. Anonymous, read-only.
- **Script:** `capture/ontokit.mjs` (re-shoot steps in `capture/README.md`).

## What the clip shows

1. **Projects.** Public projects list with one project, FOLIO.
2. **Tree.** FOLIO project (18,326 classes) with its top-level branches.
3. **Drill-down.** Area of Law (detail: definition, 12 language labels, 31 subclasses),
   then Intellectual Property Law (4 subclasses), then **Trademark and Trade Dress Law**.
4. **Concept detail.** IRI `https://folio.openlegalstandard.org/R8phitqyUIXJ4ZdLaJjabna`,
   identifier INTP-TMRK, definition, labels in pt-BR, fr, es, es-MX, de, en-GB, he, hi,
   zh, ja, parent Intellectual Property Law, Used By (9).
5. **Close.** Cursor rests on "Sign in to edit".

## Not recorded: suggest, review, merge

- **Sign-in needed.** Suggesting needs a signed-in account. Anonymous users see
  "Sign in to edit"; the project's Pull Requests page lists 0 open pull requests.
- **Credential blocked.** The auto-mode permission classifier denied reading the
  credential files' structure under the ontokit-dev config folder. Per standing rules,
  the capture did not work around it, so the clip covers browsing and concept detail only.
- **To unblock.** Add a permission rule that lets the capture script read the suggester
  credential file by path (never printed), then sign in within an unrecorded context and
  record with its saved `storageState`.

## Outputs and screening

- `media/ontokit.mp4`: 20.00 s, 353,171 bytes, 1920x1080 H.264.
- `media/ontokit-still.jpg`: 3840x2160 (deviceScaleFactor 2), JPEG q85, Trademark and
  Trade Dress Law detail.
- **Screening:** 10 frames at one every 2 s, each inspected. No keys, tokens, emails,
  names or personal data ("1 member" shows a count only). Frames deleted.
