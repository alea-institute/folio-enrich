# Part D — FOLIO ontology cleanup for the "Agreement" precision bug

**This is a self-contained handoff for a Claude Code session working in the
`alea-institute/FOLIO` ontology repo** (not folio-enrich). Open this file there, or
paste it as a prompt. It needs no prior context.

---

## Goal

The string **"Agreement"** is being mis-linked to the concept **"License (Agreement)"**
instead of the **"Agreements / Contracts"** concept. Root cause is in the ontology data:
the singular "Agreement" is an `skos:altLabel` of *License (Agreement)*, while the
*Agreements/Contracts* concept only carries the **plural** "Agreements". Plus there's a
stray duplicate placeholder concept that also claims "Agreement".

The downstream app (folio-enrich) already has a code-level workaround, but these three
edits fix the data at the source and benefit **every** FOLIO consumer. Make them in the
ontology and ship a new ontology release.

## Before you edit — find the source of truth

The published artifact is **`FOLIO.owl`** (RDF/XML, ~18 MB) at the repo root, loaded by
consumers from the repo's default branch. **First determine whether `FOLIO.owl` is
hand-maintained or generated** from another source (Protégé project, `.ttl`, CSV/sheets,
a build script, etc.):

- Check the repo `README`, a `Makefile`/build scripts, and for non-`.owl` source files.
- If `FOLIO.owl` is **generated**, edit the upstream source and regenerate — do **not**
  hand-edit the generated `.owl` (it will be overwritten).
- If `FOLIO.owl` **is** the source of truth, edit it directly (it's large — use targeted
  search/replace on the exact anchors below; don't load the whole file into context).

The three target concepts are identified by their IRI suffix. Each lives in an
`<owl:Class rdf:about="https://folio.openlegalstandard.org/<IRI>">` element.

---

## Edit 1 — Remove the singular "Agreement" alt-label from *License (Agreement)*

**IRI:** `https://folio.openlegalstandard.org/RKKRGOkIme6pnG2BSePt1Z`

Current markup (real, abridged):
```xml
<owl:Class rdf:about="https://folio.openlegalstandard.org/RKKRGOkIme6pnG2BSePt1Z">
  <rdfs:label>License (Agreement)</rdfs:label>
  <skos:altLabel>Agreement</skos:altLabel>          <!-- ← DELETE this line -->
  <skos:altLabel xml:lang="en-gb">Licence</skos:altLabel>
  <skos:altLabel>License</skos:altLabel>
  ...
</owl:Class>
```

**Action:** delete the single line `<skos:altLabel>Agreement</skos:altLabel>` **within
this class only**. Keep "License", "Licence", and all translations. (Note: there are many
bare `<skos:altLabel>Agreement</skos:altLabel>` lines across the file for different
concepts — only remove the one inside the `RKKRGOkIme6pnG2BSePt1Z` class. Anchor your edit
on the class's `rdf:about` to be safe.)

## Edit 2 — Add the singular "Agreement" to *Agreements / Contracts* (recommended)

**IRI:** `https://folio.openlegalstandard.org/R88D8i8AcSTUig2X3yPbFHg`

Current markup:
```xml
<owl:Class rdf:about="https://folio.openlegalstandard.org/R88D8i8AcSTUig2X3yPbFHg">
  <rdfs:label>Agreements</rdfs:label>
  <skos:altLabel xml:lang="en-gb">Agreements</skos:altLabel>
  <skos:prefLabel>Contracts</skos:prefLabel>
  ...
</owl:Class>
```

**Action:** add a singular alt-label inside this class:
```xml
  <skos:altLabel>Agreement</skos:altLabel>
```
This makes the singular surface form map to the correct concept *in the data* (not just
via the consumer's lemma inference). The bare (no `xml:lang`) form matches the file's
default-language convention used elsewhere in this class.

## Edit 3 — Delete (or deprecate) the duplicate placeholder concept

**IRI:** `https://folio.openlegalstandard.org/RCiAtR0akBA7apMyfjy515B`

Current markup:
```xml
<owl:Class rdf:about="https://folio.openlegalstandard.org/RCiAtR0akBA7apMyfjy515B">
  <rdfs:label>DUPE of `License `</rdfs:label>
  <skos:altLabel>Agreement</skos:altLabel>
  ...
</owl:Class>
```

This is an editorial duplicate (note the `DUPE of` label and that it carries the same
"Agreement" alt-label). **Action — pick one:**
- **Preferred:** Deprecate the entire `<owl:Class …RCiAtR0akBA7apMyfjy515B …> … </owl:Class>`
  element. Then grep the file for `RCiAtR0akBA7apMyfjy515B` and remove/redirect any
  dangling references to it (e.g. `rdfs:subClassOf`, `owl:someValuesFrom`) so the OWL
  stays valid.
- **AltLabel Removal:** Remove the `<skos:altLabel>Agreement</skos:altLabel>` line and add
  `<owl:deprecated rdf:datatype="http://www.w3.org/2001/XMLSchema#boolean">true</owl:deprecated>`.

---

## Verify

1. **Targeted checks (no full-file load):**
   - `RKKRGOkIme6pnG2BSePt1Z` class no longer contains `<skos:altLabel>Agreement</skos:altLabel>`.
   - `R88D8i8AcSTUig2X3yPbFHg` class now contains `<skos:altLabel>Agreement</skos:altLabel>`.
   - `RCiAtR0akBA7apMyfjy515B` is deprecated + no "Agreement" label, and no
     dangling references remain.
2. **XML well-formedness:** `python -c "import lxml.etree as e; e.parse('FOLIO.owl')"`
   (or `xmllint --noout FOLIO.owl`) — must parse cleanly.
3. **Release/commit** per the repo's normal process so consumers pick up the new version.

## After release — refresh folio-enrich

In the folio-enrich repo, the ontology is fetched from GitHub and cached by content hash;
a process restart (or the in-app reload path) picks up the new version. Then re-run its
regression eval — `cd backend && .venv/bin/python -m pytest tests/test_disambiguation_eval.py -m slow -v`
— and update the one tier assertion: with Edits 1–2 applied, `"agreement"` becomes a
direct alt/pref match, so `get_all_labels()["agreement"].label_type` will be
`"alternative"`/`"preferred"` rather than `"lemma_preferred"`.
