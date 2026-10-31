---
title: "Handoff: deploy the bug sweep to PROD once server access lands"
date: 2026-10-31
status: open
session: "46b5548d-6a28-58b4-86fe-f1b41cd00d0d"
written_at: "2026-10-31T18:09:40.132Z"
head: "264fc1c4c7b74945b150be43d0df2e643b7744e8"
worktree: "/home/damienriehl/worktrees/folio-enrich-citeurl-fix"
branch: "docs/handoff-prod-deploy"
---

# Handoff: deploy the bug sweep to PROD once server access lands

## State
- PR #51 (citeurl normalization) and PR #52 (repo-wide bug sweep) are merged to
  `main` (`264fc1c`). Plans: `docs/plans/2026-10-30-001-fix-citeurl-normalization-plan.md`,
  `docs/plans/2026-10-30-002-fix-bug-sweep-plan.md` (both record outcomes).
- DEV (propositions-dev) runs `264fc1c`, healthy, smoke-tested.
- PROD (enrich.openlegalstandard.org) still runs a ~July build and exposes anonymous
  `PUT /settings`, `POST /ollama/setup`, and feedback export/delete until deployed.

## Blocker
- SSH to the enrich/mapper/ontokit PROD host is closed (port 22 allowlist) and its old
  key is no longer on the home box. The separate folio-api host works.
- Damien has a drafted request to Mike asking for: SSM Session Manager (or Tailscale) on
  both FOLIO EC2 hosts; a GitHub OIDC deploy role for the openlegalstandard.org Astro
  site (S3 + CloudFront); optional Route 53 rights; and, as a stopgap, the existing
  folio-prod public key on the enrich host plus the static Hetzner IP allowlisted.
- Cockpit ask: `folio-enrich-2026-10-30-2039-prod-ssh-access` (hard block, Damien's).
- Using the folio-prod key against the enrich host needs a permission rule from Damien
  (the auto-mode classifier blocked it as credential exploration).

## Next steps once access exists
1. On the PROD host: `git pull origin main` in the folio-enrich checkout.
2. Install new deps into the uv-managed venv (no pip): openai, anthropic, markdown,
   nupunkt>=0.6 (simplest: uv pip install the backend project itself).
3. Set `FOLIO_ENRICH_ADMIN_TOKEN` in the server env (back up the env file first);
   without it the admin routes fail closed (by design).
4. Restart the folio-enrich service; verify `/health/detail` (citations ready),
   a live job with Minn. Stat./C.F.R. citations, and 403 on anonymous `PUT /settings`
   and `POST /ollama/setup`.
5. File a Cockpit outcome; retire this handoff.

## Follow-ups (not started)
- Website refresh on openlegalstandard.org (links to folio-enrich, folio-mapper,
  OntoKit, OpenGloss, screenshots/animations) once repo + deploy role access exists.
- Google default model stays `gemini-3-flash-preview`; OpenAI default `gpt-4o`
  retires 2027-01-14 (switch before then).
