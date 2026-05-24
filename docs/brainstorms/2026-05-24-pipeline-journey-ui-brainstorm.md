# Brainstorm — Process Pipeline as a "Journey" (focus + context walk)

**Date:** 2026-05-24 · **Branch:** `dev` (auto-deploys to Railway DEV) · **File:** `frontend/index.html`
**Supersedes:** `.planning/PIPELINE-UI-HANDOFF.md` (7 prior iterations) · **Next:** `/ce:plan`

## The breakthrough

Six iterations failed because they treated this as a **layout** problem (vertical/horizontal,
collapsed/expanded, chips/stepper). The user's two words — **"expand automatically"** and
**"walk along the path"** — are about **motion**, not layout. The deadlock dissolved once two
things were said plainly by the user:

- **"Collapse" = compact, never hidden.** Off-focus stages shrink; nothing disappears.
- The motion the user wants is a **horizontal journey** where the *focus travels* along the path.

## What we're building

A **focus + context horizontal journey** (macOS-Dock-magnification on a track). The pipeline is a
left→right row of 7 stage nodes. The **active stage is magnified** (bold, larger, full name +
one-line description below the track); finished and future stages stay **compact but labeled**.
As the backend advances, the magnified focus — together with a progress fill, a marker, and a live
`N / 7` count — **walks rightward along the path**. That traveling magnification *is* the "walk,"
and because it auto-follows the active stage, it *is* "expands automatically."

```
PROCESS PIPELINE                              ⤢ expand all

 ●────●────◉────○────○────○────○
 Ing  Nrm  Enrich Idn  Res  Mat  Jdg     tiny labels always; active = bold + larger
 ●━━━━━━━━━●· · · · · · · · · · ·  3 / 7  fill + marker + live count
 ▸ Identifying FOLIO concepts…           active stage's description, below the track

 ●━●━●━●━●━●━●  ✓ Complete  (holds ~2s) ──→  ✓ Pipeline complete   ⤢
```

## Why this approach

- **Matches the mental model** the user described directly (horizontal, finished-collapse,
  current-expand, position affordance, click-to-expand-all).
- **Keeps every stage name visible** (tiny labels always) — fixes the #1 recurring rejection
  ("can't see the stages") without going back to a tall vertical list.
- **Motion is real, not a class swap.** A persistent marker/fill/lozenge that *transitions its
  position* is genuinely animated — unlike today's full `innerHTML` rebuild.
- **Perceptible even on sub-second stages** via min-dwell + queue, so the walk is never skipped.

## Key decisions (locked with the user)

| # | Decision | Choice |
|---|----------|--------|
| 1 | **Motion metaphor** | Horizontal journey; focus magnification travels left→right |
| 2 | **Compact look** | **Tiny labels always** under every node; active node enlarges to full label |
| 3 | **Active detail** | Active stage's one-line description renders **below the track** (saves width) |
| 4 | **Position affordance** | Progress **fill + marker + live `N / 7` count** |
| 5 | **Expand-all** | `⤢` control opens **all** stages to full labels + descriptions (manual override) |
| 6 | **On complete** | Hold filled track **~2s**, then ease-collapse to `✓ Pipeline complete`; a `⤢` re-opens the journey on demand (nothing permanently hidden) |
| 7 | **Pacing** | **Min dwell ≥~600ms + queue** bursts so every stage visibly gets its moment |
| 8 | **Entrance** | On `phase→running`, the component eases in (height/opacity grow) = "expands automatically" *(overridable default)* |

## Constraints & build notes (for the planner — WHAT must hold)

- **Narrow left column.** 7 horizontal nodes is exactly what made 9px chips wrap. Fit relies on:
  abbreviated tiny labels for off-focus nodes (`Ing Nrm Enr Idn Res Mat Jdg`), the active full label,
  and the description dropping **below** the track — not inline. Wrapping is the failure mode to test.
- **Do NOT rebuild `innerHTML` on every status update.** Today `renderProgressStages()`
  (`index.html:5891`) replaces the whole `<ol>` each tick, so nothing persists to animate. The
  journey needs **stable DOM nodes** whose `transform`/width/position *transition* between states.
- **Stage source of truth.** 7 high-level stages
  (`ingesting,normalizing,enriching,identifying,resolving,matching,judging`) driven by the SSE
  stream — keep 7, not the finer 14 *(overridable default; 14 would crowd the narrow column)*.
- **Test conditions (the gotcha that wasted prior cycles):** verify at **http://localhost:8731** or
  Railway DEV (same-origin) with a **NEW/uncached document** — cached re-submits skip the stream and
  the journey can't walk. Confirmed `:8731` backend is healthy this session.

## Rejected (do not revisit)

Horizontal 9px chips (wrapped) · chevron "flow" connectors · horizontal node-track with
tooltip-only labels · chevron-collapsible vertical stepper · auto-collapse-on-transition ·
accordion showing one representative stage · appears-on-enrich full vertical list collapsing to a
line. **Root miss:** all of these either hid stage names or animated via class-swap on a rebuilt DOM.

## Open questions

None — all design decisions resolved with the user. Defaults marked *(overridable)* are
low-stakes and safe for the planner to assume unless the user says otherwise.
