# Collection Output Failure Recovery

## Problem

Collection may complete a billable provider request before writing the requested output. If that write fails, reporting the default `requests_made: 0` or returning without the normalized sources can prompt an operator to repeat the paid request and lose the original job/source identifiers.

## Regression

The CLI test injects a recording transport response, forces the requested library write to fail, then checks that exactly one request occurred and a private recovery library contains the normalized sources, receipt, actual request count, and job IDs.

## Solution

- Catch output persistence errors only after collection has returned.
- Serialize the complete collection library with a deterministic recovery ID.
- Write to a same-directory temporary file, fsync it, atomically hard-link it to a content-addressed final path, then fsync the directory.
- Store under `$XDG_STATE_HOME/reviews-into-fixes/recovery/`, with a per-user temporary-directory fallback. Require current-user-owned directories, directory mode 0700, and file mode 0600.
- Emit fixed structured stderr including actual request count, recovery ID/path, source IDs, and job IDs. Return failure and direct operators not to retry.
- If recovery storage also fails, report that explicitly while retaining actual counts and source/job IDs in stderr.

## Prevention

Treat successful external side effects and local artifact writes as separate failure domains. Once a paid request may have occurred, every error path must preserve the observed request count and either durably preserve the normalized receipt or clearly report the recovery failure without suggesting an automatic retry.

## Resume Correction

The same defect existed independently in resume: download timeouts, HTTP errors, malformed responses, and failed output writes reported zero or discarded the pending snapshot. Thirteen test-first cases now verify these paths through the real CLI and injected transport. Resume attaches an updated receipt to its safe transport exception, saves prior sources with that receipt, and reports both cumulative `requests_made` and `requests_this_run`. Failed downloads leave the recorded snapshot explicitly resumable with a new approval; no retry or collection trigger is performed. If writing the requested library fails, private recovery preserves the same sources, jobs, snapshot, and counts.
