# FOLIO MCP server: live session evidence

- **Collected:** 2026-11-25 (timestamp inside `mcp-transcript.json`)
- **Endpoint:** https://folio.openlegalstandard.org/mcp (Streamable HTTP)
- **Client:** Python `mcp` SDK 2.3.0 (`mcp.client.streamable_http.streamable_http_client` + `ClientSession`), Python 3.13.11, run from a throwaway venv
- **Server reported on initialize:** `name='FOLIO Legal Ontology'`, `version='1.27.0'`, protocol `2025-11-25`
- **Full raw record:** `mcp-transcript.json` (each call's name, arguments, latency, and full result; nothing trimmed, 9.3 KB)

## Sequence a lawyer's AI assistant would make

| # | Call | Arguments | Latency | What came back |
|---|------|-----------|---------|----------------|
| 1 | `tools/list` | none | n/a | 15 tools (list below) |
| 2 | `search_concepts` | `{"query": "arbitration", "limit": 5}` | 145 ms | Top hit **Arbitration Practice** (score 100.0), then Arbitration Award, Arbitration Forum, Arbitration Event (81.48 each), Arbitration Clause |
| 3 | `get_concept` | `{"iri": "https://folio.openlegalstandard.org/RXO2u2WBkUUcEG1jczLIcA"}` | 88 ms | Full record, below |
| 4 | `get_parents` | same IRI, `max_depth: 2` | 88 ms | Alternative Dispute Resolution Practice, Litigation Practice, Dispute Service, Dispute Proceeding Type |
| 5 | `get_children` | same IRI, `max_depth: 1` | 83 ms | Domain Name Dispute Resolution Practice |

## Concept chosen: Arbitration Practice (verbatim from `get_concept`)

- **IRI:** `https://folio.openlegalstandard.org/RXO2u2WBkUUcEG1jczLIcA`
- **Identifier:** `D-ADR-ARB` (hidden label `ARB`)
- **Definition:** "Arbitration, a form of alternative dispute resolution (ADR), is a way to resolve disputes outside the courts. The dispute will be decided by one or more persons (the "arbitrators", "arbiters" or "arbitral tribunal"), which renders the "arbitration award"."
- **Parent (`sub_class_of`):** `R85H4hDZWq92xwwBFP7WCtM` = Alternative Dispute Resolution Practice
- **Child (`parent_class_of`):** `RDKSHk0fleH3UJIiS4lfIzP` = Domain Name Dispute Resolution Practice
- **See also:** Arbitration Forum (`R8LtU1k4pyiSD639zaq4vrM`), Arbitration Event (`RC2LcVXjOZOiT3wqNc2SU5n`)
- **Translations (10 locales):**
  - es-es: Práctica de arbitraje
  - es-mx: Práctica de arbitraje
  - pt-br: Prática de arbitragem
  - fr-fr: Pratique de l'arbitrage
  - de-de: Schiedspraxis
  - en-gb: Arbitration Practice
  - he-il: מעשה בית דין פרטי
  - hi-in: विवाद-समाधान अभ्यास
  - zh-cn: 仲裁实践
  - ja-jp: 仲裁実務

`get_parents(max_depth=2)` returned four ancestors, with these definitions verbatim:
- Alternative Dispute Resolution Practice: "The use of methods such as mediation and arbitration to resolve a dispute instead of litigation."
- Litigation Practice: "Matters that include official proceedings (e.g., court case, arbitration, mediation)"
- Dispute Service: "A process that describes a conflict/adversarial event potentially or actually involving a second party. This can include government entity or internal investigation"
- Dispute Proceeding Type: "Dispute Proceeding Type refers to the specific legal process used to resolve a conflict between parties, such as an investigation, alternative dispute resolution, administrative proceeding, civil court proceeding, or criminal court proceeding."

## Tools the live server lists (15)

search_concepts, search_definitions, get_concept, export_concept, list_branches, get_taxonomy_branch, get_children, get_parents, get_properties, find_connections, query_concepts, query_properties, extract_concepts, extract_citations, search_expanded.

**Drift note:** the folio-mcp README heading says "Tools (12)". The live server adds `extract_concepts`, `extract_citations`, and `search_expanded`. Use "15 tools" in the deck, or update the README.

## Other concepts checked (same session, `search_concepts`)

All three have es/pt labels (confirmed through folio-python; see `sources.md`):
- Breach of Contract `RC2fjcpsEbrVvVymvt4oASx`: es-es "Incumplimiento de contrato", pt-br "Quebra de contrato"
- Damages `RCCv5YLoHUOm5AlqcCBzqGf`: es-es "Daños y perjuicios", pt-br "Danos e prejuízos"
- Trademark Infringement `RBQCFqSF0Q0sCqCcEwv2pgz`: es-es "Infracción de marca registrada", es-mx "Infracción de marca", pt-br "Violação de marca registrada"

## Reproduce

Script: a ~30-line Python client (connect, `initialize`, `list_tools`, four `call_tool` calls, then dump the JSON). It needs only `pip install mcp`. The server needs no auth.
