# Efficiency review — Proposition System Phase A

## 1. Duplicate session discovery/creation is triggered at SSE completion

**Location:** `frontend/index.html:6728-6729` and `frontend/index.html:6886`

**What to change:** Use a single completion path to call `ensurePropositionSession(false)`. The SSE `complete` handler currently starts `fetchFinalJob()` and also schedules `ensurePropositionSession(false)` directly; `fetchFinalJob()` calls the same function after loading the completed job (and the delayed final-job refresh calls it again).

**Why:** When annotation mode is enabled, the two asynchronous paths can overlap. Both can issue `GET /gold/sessions`, and if neither sees an existing session yet, both can issue `POST /gold/sessions`, duplicating network, parsing, disk writes, and potentially creating two annotation sessions for one job. The redundant direct call is also unnecessary when a session already exists. Keeping initialization after the final-job fetch preserves the visible ordering: the completed job is installed before session discovery and rendering.

**Concrete sketch:** Remove the direct scheduled call from the SSE completion handler and let the already-started final-job fetch own initialization:

```js
// SSE complete
fetchFinalJob();
// no separate ensurePropositionSession call here

async function fetchFinalJob() {
  // existing fetch/currentJob/render work
  if (propositionAnnotationMode && job.status === 'completed') {
    await ensurePropositionSession(false);
  }
}
```

If other callers require coalescing, additionally keep one in-flight promise inside `ensurePropositionSession`, returning it to concurrent callers and clearing it in `finally`.

**Confidence:** high

## 2. Expired-job cleanup rescans and reparses every gold session for every job

**Location:** `backend/app/storage/job_store.py:130`

**What to change:** Build the set of job IDs having unexported gold sessions once per `cleanup_expired()` invocation, then use constant-time membership checks inside the job loop.

**Why:** `_has_unexported_gold_session()` walks and JSON-parses the entire `gold_sessions` directory for each job. With `J` jobs and `S` sessions, the hourly cleanup performs up to `J × S` file reads/parses. This grows quadratically and repeats identical disk work even though the session set is unchanged during the cleanup pass. A one-pass index preserves the existing disk-derived, restart-safe protection behavior and all deletion ordering.

**Concrete sketch:** Add a helper that scans `gold_sessions/*.json` once and returns `{job_id for valid unexported sessions}` (continuing past malformed files exactly as today). In `cleanup_expired()`, compute `protected_gold_job_ids` before the job loop and replace `self._has_unexported_gold_session(path.stem)` with `path.stem in protected_gold_job_ids`.

**Confidence:** high

## 3. Filtering sessions by job ID still loads, migrates, validates, and deep-copies every session

**Location:** `backend/app/services/gold/store.py:254`

**What to change:** Maintain a lightweight job-to-session index at save time, or store sessions under a job-addressable layout/index, so `list(job_id)` resolves only matching session files. Keep the current full scan for unfiltered listing and preserve `_load()` plus `_public_session()` for each returned match.

**Why:** The frontend calls `GET /gold/sessions?job_id=...` whenever it ensures an annotation session. The server nevertheless walks every session file and calls `get()`, which reads the full JSON, migrates every proposition payload, validates the complete Pydantic model, and deep-copies it for blind-segment redaction before discarding nonmatching sessions. Cost and memory churn therefore scale with all historical annotation sessions rather than the requested job's sessions.

**Concrete sketch:** Write an atomic sidecar index such as `{job_id: [session_id, ...]}` whenever `_save()` creates a session. For `list(job_id)`, iterate only those IDs and call the existing `get(session_id)`; for `list(None)`, retain the current sorted directory scan. Rebuild or fall back to the full scan when the index is absent/corrupt so observable results, error tolerance, sorting, migrations, and blind redaction remain unchanged.

**Confidence:** medium
