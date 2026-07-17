# folio-enrich -> folio-resolve: Classified Delta Report

- Corpus hash match (baseline vs candidate): **True**
- folio_resolve present: baseline=False, candidate=True
- FOLIO concepts: 18326

## Headline (label resolution)

- Intended fixes: **5**
- Regressions: **0**
- Neutral changes: **7**

## Canaries

- Place/agency mis-maps (generic terms): **3 -> 0** (target: -> 0)
- New place mis-maps introduced (must be empty): `[]`
- Named recoveries dropped (must be empty): `[]`
- **CANARY PASS: True**

## Label-resolution deltas (before -> after)

| id | category | bucket | why | baseline | candidate |
|----|----------|--------|-----|----------|-----------|
| lr-compound-arbmed | compound_multihead | **intended_fix** | compound decomposition candidates gained=5 | 'Judicial Arbitration and Mediation Services' [Forums and Venues] conf=0.952 | 'Arbitration Practice' [Service] conf=1.0 |
| lr-exact-lawyer | exact | **intended_fix** | recovery resolves to a label sharing more query words (0->1) | 'Legal Aid Attorney' [Engagement Terms] conf=0.892 | 'Lawyer' [Engagement Terms] conf=1.0 |
| lr-homonym-justice | homonym_trap | **intended_fix** | place/agency mis-map replaced by non-place concept | 'U.S. Dept. of Justice' [Governmental Body] conf=0.892 | 'Obstruction of Justice' [Objectives] conf=0.794 |
| lr-homonym-tax | homonym_trap | **intended_fix** | place/agency mis-map replaced by non-place concept | 'U.S. Tax Court' [Governmental Body] conf=0.952 | 'Tax Practice' [Service] conf=0.99 |
| lr-place-decisionmaker | place_agency_generic | **intended_fix** | place/agency mis-map replaced by non-place concept | 'U.S. Army Intelligence and Security Command' [Governmental Body] conf=0.6 | 'Arbitration and Award' [Objectives] conf=0.468 |
| lr-exact-hearing | exact | **neutral** | recovery IRI changed, equal query-word overlap | 'Markman Hearing' [Event] conf=0.952 | 'Hearing' [Event] conf=1.0 |
| lr-fuzzy-arbrules | fuzzy | **neutral** | recovery IRI changed, equal query-word overlap | 'AAA Labor Arbitration Rules' [Legal Authorities] conf=0.952 | 'Rules of Arbitration' [Legal Authorities] conf=0.95 |
| lr-homonym-action | homonym_trap | **neutral** | resolution changed (both non-place) | 'Concert of Action Crimes' [Objectives] conf=0.892 | 'Private Right of Action' [Objectives] conf=0.727 |
| lr-homonym-charge | homonym_trap | **neutral** | resolution changed (both non-place) | 'Fee Charge Date' [Engagement Terms] conf=0.892 | '"Encumbrance" Definition' [Objectives] conf=1.0 |
| lr-homonym-law | place_agency_generic | **neutral** | resolution changed (both non-place) | 'Offices of Lawyers' [Industry] conf=0.776 | 'Lawyer' [Engagement Terms] conf=0.776 |
| lr-homonym-state | homonym_trap | **neutral** | resolution changed (both non-place) | 'State Court' [Forums and Venues] conf=0.952 | 'Estate' [Asset Type] conf=0.99 |
| lr-proposed-novelterm | proposed_class | **neutral** | resolution changed (both non-place) | 'Export Controls Practice' [Service] conf=0.886 | 'Compliance' [Objectives] conf=0.913 |

## Entity-ruler deltas

_No changes._


## Reconciler deltas

_No changes._


