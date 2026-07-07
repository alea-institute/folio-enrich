# Third-Party Licenses & Attribution

folio-enrich is licensed **MIT** (see `LICENSE`). It incorporates the
open-source components and openly-licensed data below.

## Openly-licensed data

### FOLIO ontology — CC-BY 4.0
Documents are annotated against **FOLIO** (Federated Open Legal Information
Ontology), maintained by the **ALEA Institute**, originating from the **SALI
Alliance**; consumed via `folio-python`. Licensed **CC-BY 4.0**.
- Source: https://github.com/alea-institute/FOLIO · License: https://creativecommons.org/licenses/by/4.0/

## Vendored assets

- **flag-icons** SVG artwork (MIT) — bundled in `frontend/index.html`; full text
  in `LICENSES/flag-icons-LICENSE.txt`.

## Notable dependencies

| Component | License | Notes |
|-----------|---------|-------|
| fastapi, folio-python[search], spacy, markdown-it-py, nupunkt, citeurl, faiss-cpu, openpyxl | MIT | permissive |
| pyahocorasick, rdflib, sse-starlette, psutil, eyecite | BSD | permissive |
| **pypdf** | BSD | **PDF text extraction** (replaced PyMuPDF — see below) |
| pyarrow | Apache-2.0 | permissive |
| striprtf, beautifulsoup4, python-docx | MIT/BSD | permissive |
| **olefile** | BSD | **Outlook `.msg` parsing** (replaced extract-msg — see below) |

## Removed for license hygiene

- **PyMuPDF (AGPL-3.0)** was removed 2026-07-05 (Damien-approved) and replaced
  with **pypdf** (BSD) for PDF text extraction, keeping folio-enrich cleanly
  MIT-compatible. See the portfolio OSS-license audit
  (`EP-PORTFOLIO-OSSLICENSE-001`).
- **extract-msg (GPL-3.0)** was removed 2026-07-06 (Damien-approved) and replaced
  with a small **olefile** (BSD) reader for Outlook `.msg` parsing. `_ingest_msg`
  now reads the MAPI property streams (subject/sender/to/body + submit-time)
  directly, keeping folio-enrich cleanly MIT-compatible. Added `.msg` parsing
  tests (`test_msg_ingestor_*`) that the GPL path never had.
