---
title: "refactor: replace the spaCy EntityRuler with a token-aligned Aho-Corasick matcher"
type: refactor
status: completed
date: 2026-11-07
---

# refactor: replace the spaCy EntityRuler with a token-aligned Aho-Corasick matcher

## Problem

The cached FOLIO `FOLIOEntityRuler` (spaCy `entity_ruler` over a blank English
pipeline) costs about 530 MB of RSS (2026-11-04 measurement: FOLIO graph + labels
356 MB, ruler bundle 884 MB). PROD's enrich process peaks at 2.47 GB on an 8 GB box
shared with folio-mapper, ontokit and Caddy. DEV's container (1600 MB) can run only
one both-mode pipeline at a time. The ruler is the largest single resident cost we
control.

## Behaviour to preserve exactly

`FOLIOEntityRuler.find_matches(text)` returns `EntityRulerMatch(text, start_char,
end_char, label, entity_id, match_type)` with these semantics:

- **Tokenization:** text is tokenized by `spacy.blank("en")`'s tokenizer. Whitespace
  runs beyond a single space become their own tokens, and they break a match.
- **Patterns** (`pattern_builder.build_patterns`): one per label key (stopwords and
  keys shorter than 3 characters are skipped). Each pattern carries the id
  `iri|label_type`.
  - **Single-word labels** are phrase patterns. The label is tokenized by the same
    tokenizer and matched on the token sequence's `LOWER` values.
  - **Multi-word labels** are token patterns: `label.split()`, each element matched
    against one token's `LOWER`. A whitespace-split element with attached
    punctuation (for example `(agreement)`) never equals a spaCy token, so such
    labels never match today.
- **Overlaps** follow `EntityRuler.match` plus `set_annotations`: candidates sort
  by (token length descending, start ascending). A candidate is kept only if none of
  its tokens belongs to an already-kept span.

## Approach

Build the matcher from a pyahocorasick automaton (already a dependency, used by
`property_matcher`):

1. Encode each pattern as its token-`LOWER` sequence joined by a separator character
   that cannot occur in a token. The payload is `(iri, label_type)`.
2. At match time, tokenize the text with the same blank tokenizer, build the joined
   lowercase token string with a character-offset map back to the source text, run
   the automaton, and keep only hits that start and end on token boundaries.
3. Apply the overlap rule above, then return the same `EntityRulerMatch` objects.
4. Swap it in behind `FOLIOEntityRuler`'s interface (`load_patterns`,
   `find_matches`), so `_RulerBundle`, `_UnionRulerBundle`, the union merge and all
   callers keep working. Update every caller that reaches into spaCy internals.

## Verification (the gate)

- **Equivalence:** for every baked demo text, in folio, canon and both modes, the old
  spaCy ruler and the new matcher return identical lists of `(start_char, end_char,
  entity_id, match_type)`. Any difference blocks the change until it is explained and
  fixed.
- **Unit tests** for the semantics above: multi-space break, a hyphenated single-word
  label, a punctuation-attached multi-word label that does not match, the overlap
  ordering, and offsets on text with non-ASCII characters.
- **Memory:** RSS after the FOLIO ruler bundle builds, old vs new, on the same
  machine, plus the both-mode union bundle.
- **Speed:** wall time for `find_matches` on the largest demo, old vs new.
- **Suite:** the full backend suite passes.
- **Deploy:** DEV and PROD peak RSS during a both job, compared with 2026-11-04.
  On DEV, set `FOLIO_ENRICH_MAX_PARALLEL_PIPELINES` back to 2 only if two concurrent
  cold both jobs then stay under the container limit.

## Sequencing

This lands after the translation alt-label fix
(`2026-11-07-0745-fix-translation-alt-label-leak-plan.md`), because that fix changes
the label set the equivalence gate measures.

## Rollback

Revert the merge commit; nothing persistent changes.

## Results (2026-11-07)

Shipped in PR #63 (`29846fd`), with an explicit tie rule: the preferred label wins an identical token sequence, then the first added; spaCy left this to set order. The real ontologies have one such case, "investigator / examiner": the same concept appears as both preferred and alternative.

- **Equivalence:** across all 34 baked demo texts in folio, canon and both modes, the output is identical to the spaCy ruler (3,934 / 3,625 / 4,438 matches, zero differences).
- **Local memory:**
  - FOLIO ruler: 256 → 69 MB.
  - Process peak (folio + canon + both bundles): 1,004 → 655 MB.
- **Speed:** matching runs 1.08 → 0.23 s across the 34 texts, about 4.7× faster.
- **DEV:** a cold both job on the regulatory memo peaks at 908 MiB, inside a 1.56 GiB limit (it was 1.46 GiB on 2026-11-04). The job returned 270 annotations, the same as before the change, in 16 s.
- **PROD:** service peak 2.18 GB (it was 2.42 GB on the previous build and 2.47 GB on 2026-11-04).
  - Results are unchanged: the both job returns 280 and the FOLIO job 250.
  - The admin gate still returns 403, the logs show zero errors, and the neighboring services stay active.
- **PROD rollback:** a dated `enrich-backup-<ts>-pre29846fd` holds HEAD and `.env`. There were no dependency changes. To roll back, run `git checkout 3dc214d` and restart.

DEV still runs with `FOLIO_ENRICH_MAX_PARALLEL_PIPELINES=1`. The measured headroom (about 650 MB on a cold both job) suggests 2 now fits, but that is a `.env` change, so it waits for a separate okay.
