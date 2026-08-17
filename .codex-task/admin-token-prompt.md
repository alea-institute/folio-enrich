# Task — frontend admin-token support for /gold routes (folio-enrich, branch main)

The /gold annotation routes are gated by `require_admin` (backend/app/api/auth.py): when the server sets `admin_token`, requests must carry a matching `X-Admin-Token` header. The frontend (single-file frontend/index.html) never sends it, so annotation breaks on deployed instances.

**No git. No network.** Report -> `.codex-task/admin-token-report.md` (summary, files, verification).

## Build

1. In the Propositions tab header area (near the Annotation mode toggle), add a small "Admin token" password-type input + save affordance, persisted to `localStorage` key `folioEnrichAdminToken` (client-side only, mirroring how the BYOK API key persists client-side). Pre-fill from localStorage on load. Add a one-line hint: "Required on deployed instances; leave empty locally."
2. `propositionFetch` (and ONLY the /gold-calling paths) attaches `X-Admin-Token: <token>` when a token is stored. Do not attach it to non-/gold requests.
3. On a 401/403 from /gold, surface the server detail via the existing toast AND focus the admin-token input.
4. Match existing conventions (styles, escapeHtml, no framework).

## Verify
- Extract each inline <script> block, `node --check` each; grep for duplicate ids among added elements.
- Backend contract sanity: cd backend && .venv/bin/python -m pytest tests/test_gold_store.py -q (unchanged, must stay green).
