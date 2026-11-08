---
artifact_contract: "ce-handoff/v1"
title: "folio-enrich: demo-tag accuracy pass — checkpoint"
summary: "Eval set built and measured; Codex worker implementing fork gate, Delaware homonym, deictic courts, eval scorer on session/1108-1406."
keywords: ["folio-enrich","demo-tags","eval-set","fork-gate"]
resume_focus: "Verify worker commits, replay demos, re-measure, review, PR, DEV, PROD"
---
# Checkpoint: demo-tag accuracy pass

- **Branch:** session/1108-1406 in this worktree, reset to origin/main fc3c8fe, plus commit 31d01d0 (plan + gold labels). Not pushed yet.
- **Plan (results + decisions):** docs/plans/2026-11-08-1430-fix-demo-tag-accuracy-plan.md.
- **Gold labels:** backend/eval/demo_tags/labels.json (1,536 verdicts). Baseline precision 0.61; fork fallback 0.33 is the largest class.
- **Worker:** Codex via cockpit worker-wrapper, task a cockpit worker task Report file: backend/.worker-report-demo-tag-accuracy.md (untracked).
- **Next:** verify commits + suite; `scripts/replay_fix_demos.py` under box-run (needs sentence-transformers only if label set changes — it isn't in the venv); rerun `scripts/demo_tag_eval.py`; label any unlabeled new tags; ce-code-review; PR; CI; DEV propositions-dev; PROD per the 2026-11-07 deploy recipe.
- **Venv:** backend/.venv built with uv sync --frozen --extra dev + spaCy wheel 3.8.0.
