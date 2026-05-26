# Part D — Upstream FOLIO ontology data cleanup

**Repo:** `alea-institute/FOLIO` (the OWL ontology source — **not** this codebase)
**Context:** Belt-and-suspenders cleanup for the "Agreement" → "License (Agreement)"
precision bug. The app-side fix (folio-enrich `fix(folio): resolve "Agreement"…`,
commit `fb3497c`) already resolves the bug robustly via lemma reachability + index
priority, so these edits are **not urgent** — but they remove the bad data at the
source and benefit every FOLIO consumer (not just Enrich).

Verified against live FOLIO data on 2026-05-26.

---

## Edit 1 — Re-home the singular "Agreement" alt-label off "License (Agreement)"

**Concept:** `License (Agreement)` — IRI
`https://folio.openlegalstandard.org/RKKRGOkIme6pnG2BSePt1Z`

**Current state:**
```
skos:prefLabel  (none)
rdfs:label      "License (Agreement)"
skos:altLabel   "Agreement", "Licence", "Licencia", "License", "Licença",
                "Lizenz", "רישיון", "लाइसेंस", "ライセンス", "许可证"
branch          Objectives
```

**Problem:** the bare singular `skos:altLabel "Agreement"` makes any mention of
"Agreement" resolvable to *License*. A license is a *kind of* agreement, not a
synonym for "Agreement".

**Change:** **remove** `skos:altLabel "Agreement"` from this concept. Keep
"Licence"/"License"/translations. (Leave "License (Agreement)" as the rdfs:label.)

---

## Edit 2 — Add the singular "Agreement" to the Agreements/Contracts concept (optional but recommended)

**Concept:** `Agreements` / `Contracts` — IRI
`https://folio.openlegalstandard.org/R88D8i8AcSTUig2X3yPbFHg`

**Current state:**
```
rdfs:label       "Agreements"           (plural)
skos:prefLabel   "Contracts"
skos:altLabel    "Accords", "Acordos", "Acuerdos", "Agreements",
                 "Vereinbarungen", "הסכמים", "समझौते", "协议", "合意書"
branch           Document / Artifact
```

**Problem:** the singular surface form "Agreement" is not a label here at all — it's
only reachable via lemma inference (which the app now does). Adding it as an explicit
alt-label makes the mapping correct in the data itself, independent of any consumer's
normalization.

**Change:** **add** `skos:altLabel "Agreement"` (singular) to this concept.

---

## Edit 3 — Remove or deprecate the DUPE placeholder concept

**Concept:** IRI
`https://folio.openlegalstandard.org/RCiAtR0akBA7apMyfjy515B`

**Current state:**
```
rdfs:label / prefLabel   "DUPE of `License `"
skos:altLabel            "Agreement"
branch                   (empty)
owl:deprecated           (not set)
```

**Problem:** an editorial duplicate placeholder that leaked into matching because it
isn't flagged `owl:deprecated` and has no branch. It also carries the misleading
"Agreement" alt-label.

**Change:** **delete** this concept, or if it must be retained for history, set
`owl:deprecated true` and remove the `skos:altLabel "Agreement"`.
*(The app already filters any concept whose label contains "DUPE", but fixing the
source is cleaner.)*

---

## How the running app picks up these changes

`folio-enrich` loads FOLIO from the GitHub `main` branch and caches the OWL locally.
After the ontology repo updates:
- A fresh process start, or the in-app `_reload()` path (ontology-update flow),
  rebuilds the label index and re-keys the lemma disk cache by the new `owl_hash`.
- No code change needed in folio-enrich.

## Verify after applying

In `folio-enrich/backend`:
```bash
.venv/bin/python -m pytest tests/test_disambiguation_eval.py -m slow -v
```
The anchor tests should still pass. With Edits 1–2 applied, `"agreement"` will be a
direct alt/pref match (not just a lemma match), so `get_all_labels()["agreement"].label_type`
becomes `"alternative"`/`"preferred"` rather than `"lemma_preferred"` — update
`test_anchor_agreement_resolves_to_agreements` if you assert on the tier.
