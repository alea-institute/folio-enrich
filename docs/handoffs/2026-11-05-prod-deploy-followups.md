# Handoff: PROD deployed; follow-ups

## State
- folio-enrich PROD runs main 9a28361 (was 8695065, July). folio-api PROD runs 49b5a29.
- DEV runs 9a28361 with `FOLIO_ENRICH_MAX_PARALLEL_PIPELINES=1`.
- Receipt: docs/plans/2026-11-04-2200-chore-prod-deploy-enrich-and-folio-api-plan.md.

## Next steps
1. folio-mcp: allow the public Host header so `POST /mcp` on folio.openlegalstandard.org stops answering 421.
2. When Mike's Tailscale lands, switch the `folio-prod` / `enrich-prod` SSH aliases to tailnet names and drop the ProxyJump.
3. Memory: the cached FOLIO spaCy ruler costs ~530 MB; an Aho-Corasick matcher (pyahocorasick is already a dependency) should cut that sharply. Gate it on the 23-demo equivalence check (3,973 identical matches) used for #54.
4. After a quiet week on PROD, delete the dated pre-deploy venv copy and backup dir on the enrich box.
5. Consider required status checks on main (alea-institute settings; needs Damien's okay).
