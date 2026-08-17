# Admin-token support report

## Summary

- Added a compact password-type Admin token control with a Save button and deployment hint beside the Propositions annotation controls.
- Persists the token client-side under `folioEnrichAdminToken` and restores it on page initialization. Saving an empty value clears the stored token.
- Adds `X-Admin-Token` only when `propositionFetch` is calling a `/gold` path and a token is stored. Non-`/gold` calls, including the Propositions `/settings` calls, do not receive the header.
- Preserves backend error detail in the existing information toast. A `/gold` 401 or 403 also focuses the Admin token input so the credential can be corrected immediately.

## Files

- `frontend/index.html` — Admin-token UI, localStorage helpers, scoped request header, and auth-error focus behavior.
- `.codex-task/admin-token-report.md` — this implementation and verification report.

## Verification

- Extracted both inline `<script>` blocks from `frontend/index.html`; `node --check` passed for each block.
- Duplicate-ID grep for the added elements passed: `propositionAdminTokenInput` appears once and `propositionAdminTokenHint` appears once.
- Backend contract sanity passed: `cd backend && .venv/bin/python -m pytest tests/test_gold_store.py -q` → `12 passed in 0.08s`.
- Code-level scope check confirms the token header assignment is inside `if (path.startsWith('/gold'))`; the existing non-gold `/settings` calls continue through the same helper without the header.

No Git or network operations were performed.
