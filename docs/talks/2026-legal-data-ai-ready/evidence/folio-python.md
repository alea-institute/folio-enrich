# folio-python: live demo evidence

- **Collected:** 2026-11-25
- **Package:** `folio-python` 0.4.2 from PyPI, Python 3.13.11, throwaway venv
- **Script:** `../tools/folio_python_demo.py` (9 lines of code)
- **Ontology source:** the library's default, the GitHub repo `alea-institute/FOLIO`, branch `2.0.0` (from `inspect.signature(FOLIO.__init__)`)

## Install note

A bare `pip install folio-python` prints `Disabling search functionality: rapidfuzz not found` and `marisa_trie not found`. For `search_by_label` to work, I also installed `rapidfuzz` and `marisa-trie`. The remaining stderr line, `Disabling search functionality: alea_llm_client not found.`, only affects the LLM search path, which this demo skips.

## Command

```
python docs/talks/2026-legal-data-ai-ready/tools/folio_python_demo.py
```

## Real stdout (exit 0)

```
Loaded 18,323 concepts in 0.7s
Arbitration Practice | https://folio.openlegalstandard.org/RXO2u2WBkUUcEG1jczLIcA | score 100
es: Práctica de arbitraje | pt: Prática de arbitragem
parents: ['Alternative Dispute Resolution Practice']
```

## Load time

- **Warm cache (default `FOLIO()`):** 0.7 s and 0.8 s across two runs
- **Cold, `FOLIO(use_cache=False)`:** 1.0 s and 1.7 s across two runs (this includes downloading the OWL file from GitHub and parsing it)
- **Honest framing for the slide:** "loads all 18,323 concepts in under 2 seconds"

Results match the MCP server exactly (same IRI, labels, and parent).
