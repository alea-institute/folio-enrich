---
title: "fix: citeurl citation normalization silently skipped"
status: completed
date: 2026-10-30
---

# fix: citeurl citation normalization silently skipped

## Problem
`backend/app/services/individual/citation_extractor.py` imports `citeurl` lazily and,
on `ImportError`, logs a warning and skips normalization. citeurl 12.x imports the
`markdown` package (`citeurl/mdx.py`) without declaring it, so in the locked backend
environment `import citeurl` raises `ModuleNotFoundError: No module named 'markdown'`
and statute/regulation citations (Minn. Stat., C.F.R., U.S.C.) are never extracted.

Second defect found while reproducing: `normalized_form` was set from `str(cite)`,
which citeurl defines as the matched text, so citeurl never produced a normalized
form even when it imported. citeurl's canonical form is `Citation.name`.

Third: extra citations were located with `text.find(matched)`, which maps repeated
citations to the first occurrence. citeurl exposes `Citation.span`.

## Changes
1. Declare `markdown>=3.7,<4` (BSD-3-Clause) in `backend/pyproject.toml`; log it in
   `THIRD-PARTY.md`. citeurl was already declared.
2. A missing or broken citeurl is a loud failure: `logger.error` plus a degraded-mode
   signal, not a warning-only skip.
3. Use `cite.name` for `normalized_form` and `cite.span` (offset by chunk start) for spans.
4. Performance: citeurl cost grows superlinearly with input length (~16 s for one
   222 KB call vs <1 s as section-sized calls). Run `list_cites` per paragraph-sized
   chunk and offset spans.
5. Regression tests: citeurl imports; Minn. Stat. / C.F.R. normalize with URLs;
   repeated citations get distinct spans; chunked extraction matches offsets.
6. Document known citeurl limits with tests (not fixed here): drops `subd. 3(a)`,
   collapses `§§` ranges to the first section, reads `Minn. R. Civ. P. 56.01` as
   `Minn. Stat. § 56.01`.

## Outcome (2026-10-30)
- Reproduced: `ModuleNotFoundError: No module named 'markdown'` on `import citeurl`;
  the extractor logged the skip warning and emitted no Minn. Stat. / C.F.R. citations.
- After the fix: both citations extracted with revisor.mn.gov / eCFR URLs; full backend
  suite 1251 passed; the new tests fail 10/11 with `markdown` uninstalled.
- A 210 KB synthetic document extracts in 1.3 s (600 citations) with chunking.
- Trade-off: chunking resets CiteURL's short-form/"id." context at chunk boundaries
  (8000-char chunks on paragraph breaks), so a short form whose full cite sits in an
  earlier chunk goes unresolved. Eyecite's bare "§" FullLawCitation match still appears
  beside the fuller CiteURL citation (pre-existing; follow-up candidate).
