# Verification

Verification date: 2026-10-05. All commands ran from the repository root unless an absolute temporary path is shown.

## Current Release Approvals

- The user's final release instruction reports core QA **SHIP**, security **SHIP**, and brand **SHIP**. Reviewer artifact paths were not supplied; these are recorded as user-reported approvals, not newly performed reviews.
- The user separately reports skeptic, engineer, and brand approval for all five portable skills. This release includes only the unchanged `review-next-check` skill and its approved README/example integration. The six Reviews files match the final integration manifest at `/tmp/opencode/four-repo-skills-final-20261005.json`.
- Public publication is explicitly authorized at `yaronbeen/bright-data-reviews-into-fixes`. Distribution/CLI `reviews-into-fixes` and module `reviews_into_fixes` are unchanged. No other repository or global skill installation is in this release's scope.
- Independent R3 runtime **PASS / GREEN** supersedes the historical RED candidates. The preserved report at `/home/yaron/.claude/data/brightdata-drafts/2026-10-05-reviews-independent-release-verification.md`, section `Final R3 GREEN Verification`, records 187 source tests, 187 clean-wheel tests, and the canonical case passing once in each environment. The private report and all candidate artifacts remain local and are not publication payloads.
- Live Web Unlocker remains disabled. Live provider behavior and paid-account compatibility remain unverified; offline or mocked checks do not certify them.

## Publication Preflight

Fresh execution on 2026-10-05, before staging or publication:

```text
Source release suite; network guard=EPERM; credential-free
187 passed in 0.84s
Offline CLI checks=9/9 PASS; golden bytes=3/3 PASS
collision bytes unchanged; dry/error outputs absent; requests=0
approved_file_hashes=6; local_links=14
example_exact_quotes=5; example_locators=5; frontmatter=PASS
readme_snippet=unchanged
TruffleHog 3.94.1: verified_secrets=0; unverified_secrets=0
```

The source suite and CLI subprocesses ran with a sanitized environment and libseccomp denial of `connect`, `sendto`, and `sendmsg`. The source import path was asserted. CLI checks exercised version, analysis, analysis dry-run, offline collection planning, rejected fixture live dry-run, output collision, invalid analysis input, missing resume gates, and invented provider import. All three original goldens were compared again after the collision. Compilation exited 0 with caches outside the repository.

The secret scan targeted only `git ls-files --cached --others --exclude-standard`, without scanner exclusions, with verification and updates disabled. The additional private-key/provider/GitHub/AWS/bearer fixed-pattern scan found no matches. The exact R3 wheel still hashes to `21bee0cc67f25a00db7e9a7c4b794fb567357d9165847fc04a9b0fa83e9a72b9`; all 26 bound source/test/fixture/configuration checksums returned `OK`.

Local Git already existed on `main`, with no commits, empty index, and no remote. Authenticated GitHub owner was verified as `yaronbeen`; the exact target returned 404 before creation. Normal executable pre-commit/pre-push hooks were configured and not bypassed. The following post-push record supersedes this preflight's then-pending publication checks.

## Public Publication Verification

- Public repository: https://github.com/yaronbeen/bright-data-reviews-into-fixes. `gh repo view` returned `visibility: PUBLIC`, `isPrivate: false`, and default branch `main`.
- Source publication commit: `869e165cc14a9b6ec21de9d813524ce0dec1edab` (`Publish Reviews Into Fixes showcase`). Local HEAD, GitHub `refs/heads/main`, and the unauthenticated clone matched this exact commit. Subsequent closeout changes affect release records only, not source, tests, CI, fixtures, README, or the approved skill/docs.
- Before committing, the actual 55-file staged inventory was checked: six package modules, nine existing test modules, six invented fixture/golden files, 12 handovers, and the intended package/configuration/project/solution/skill documentation. Every staged blob matched its working file; all 26 R3 bound blobs and six approved documentation blobs matched their recorded hashes. No symlinks, generated artifacts, wheels/candidates, environments, caches, actual approval/receipt/library files, or private evidence were staged.
- Normal commit and push hooks ran; no hook bypass, scanner exception, or amend was used, and no global/hook Git configuration was changed. `gh repo create --public --source /home/yaron/projects/bright-data-reviews-into-fixes --remote origin --push` created the exact repository and established `main` tracking `origin/main`.
- Unauthenticated raw README, skill, and checked-example downloads matched their approved SHA-256 values, respectively `f841b9302f09e76caf456b13c2ffdc0938ca60ab4db35d37b7370266503375b8`, `e9379343fc3e8602b5101bdb242c5d86ec0afdc3313d4160718345bbd3cf7a25`, and `cfcdd7769ece5bcbe3dc383d368e3efe12846a26917bd37d1d695eef2c84d168`.
- Fresh unauthenticated HTTPS clone: `/tmp/opencode/reviews-publication-20261005-shDNSV/public-clone`. Clone used a credential-free environment and temporary home, disabled system/global Git configuration, an empty credential helper, and no terminal prompt. Test/CLI runs asserted the clone package path and denied network syscalls; they did not import the original project source.

```text
Unauthenticated public clone suite; clone import asserted
187 passed in 1.70s
Unauthenticated clone offline CLI=9/9 PASS; goldens=3/3 PASS
collisions unchanged; dry/error outputs absent; requests=0
network syscalls denied

GitHub CI, source publication commit:
Python 3.12: 187 passed in 0.81s
Python 3.11: 187 passed in 0.88s
Both package installs, wheel builds, and console versions passed
reviews-into-fixes 0.1.0
```

Observed source-commit CI: https://github.com/yaronbeen/bright-data-reviews-into-fixes/actions/runs/37362729372, conclusion `success`, both jobs completed successfully. GitHub emitted non-blocking action-runtime deprecation and upcoming `ubuntu-latest` migration annotations; these are follow-up maintenance, not failed checks. The documentation-only closeout push receives its own normal hooks and final-HEAD checks. No paid/live provider request, global skill installation, or other repository action occurred. Live Web Unlocker remains disabled and provider/account compatibility remains live-unverified.

## Current Candidate R3

Minimal authorized showcase fix: resume passes the matching validated canonical entry from `planned_jobs` into the existing shared normalizer. Raw `original_job` URLs, manifest bytes/hash, and all tests remain unchanged. No new feature or test matrix; no README/skills/docs-worker file edits.

```text
$ PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p no:cacheprovider tests/test_resume_canonical_targets.py --tb=short
1 failed in 0.07s  (before the two-line production correction)
1 passed in 0.06s  (after the correction)

$ PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p no:cacheprovider tests --tb=short
187 passed in 1.22s

Fresh final installed wheel, single regression:
1 passed in 0.03s
Installed module isolation: PASS; kernel network denial active

Fresh final installed wheel, full suite:
187 passed in 1.15s
Installed module isolation: 5 of 5 PASS; kernel network denial active
```

Installed runners used `install-final/bin/python -IB`, sanitized environment, pytest cache/autoload disabled, `--import-mode=importlib`, and libseccomp denial of `connect`/`sendto`/`sendmsg`. The single-case and full-suite runs were separate processes. Only host pytest dependency paths were added; all application modules originated in the fresh installation.

- Final wheel: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r3/reviews_into_fixes-0.1.0-py3-none-any.whl`.
- SHA-256: `21bee0cc67f25a00db7e9a7c4b794fb567357d9165847fc04a9b0fa83e9a72b9`.
- Clean install: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r3/install-final/`.
- Canonical regression SHA-256: `946988d55423d8e12eee55c14b703c1b3ffebe720f21a55384d7fe381bd1b1ae` (unchanged).
- Source and final installed compilation: exit 0.
- Final clean `pip check`: `No broken requirements found.`
- Final installed CLI: nine of nine checks pass, versions `reviews-into-fixes 0.1.0`; no unintended dry-run/error output files.
- Final installed demo: three cards, `status: ok`, zero requests. `diff -ru` against all three original goldens: no output, exit 0.
- Source and final installed application/metadata secret scans: zero verified and zero unverified findings.
- Docs worker updated README while the initial R3 build ran. Final wheel rebuilt once without editing README; packaged and current README hashes both equal `f841b9302f09e76caf456b13c2ffdc0938ca60ab4db35d37b7370266503375b8`.
- Wheel/source checksums saved beside the R3 artifact; earlier candidates remain intact.
- Historical R3 builder status: no paid calls, nested review, remote, commit, push, or publication in that build pass. Its pending focused-approval gate is superseded by the current final approvals and explicit publication authorization above.

Exact build/install commands (repository root for build):

```bash
python3 -m pip wheel --no-index --no-build-isolation --no-deps --wheel-dir /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r3 .
python3 -m venv /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r3/install-final
/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r3/install-final/bin/python -I -m pip install --no-index --no-deps --no-cache-dir /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r3/reviews_into_fixes-0.1.0-py3-none-any.whl
```

## Historical Candidate R2

This is the replacement for the independently rejected first candidate. Reproduced defects were authorized for repair; no new feature work, helper/reviewer dispatch, test edits, README edits, or edits to the separate docs worker's files were performed.

Independent RED source: `/home/yaron/.claude/data/brightdata-drafts/2026-10-05-reviews-independent-release-verification.md`. The independent regression file remains unchanged with SHA-256 `ba6c502257a2e383ee948581a5791a680eb6c013ed9fe7f4c88afc22431e21b1`; all seven original test files also retain their previous hashes.

```text
$ PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p no:cacheprovider tests/test_resume_mapping_regressions.py --tb=line
19 failed, 4 passed in 0.42s  (before production fixes)

$ PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -p no:cacheprovider tests/test_resume_mapping_regressions.py --tb=short
23 passed in 0.25s          (after production fixes)

Full source suite, with kernel network denial:
186 passed in 0.96s

Fresh installed wheel, independent regression file:
23 passed in 0.27s
Installed module isolation: 5 of 5 PASS

Fresh installed wheel, entire suite:
186 passed in 0.94s
Installed module isolation: 5 of 5 PASS
```

Source and installed full-suite runners blocked `connect`, `sendto`, and `sendmsg` using libseccomp. Installed runners used the fresh venv interpreter with `-IB`, sanitized environment, pytest autoload/cache disabled, and `--import-mode=importlib`; only host test-runner dependency paths were appended. No project source directory was on `sys.path`, and every loaded application module was verified to originate in the fresh installation.

Scope of repair: collect and resume reuse the same approved-target mapping/provider-error exclusion function; cross-URL review IDs remain independent; real urllib normal/error-body reads normalize HTTPException/IncompleteRead; wrapped timeout reasons remain completion-unknown; decoder recursion is handled inside the post-dispatch receipt boundary. Existing durable output/recovery paths receive the correct counted receipts with prior sources, jobs, and snapshot IDs. Exactly one call per invocation, with no retry/retrigger, is asserted by the unchanged tests.

Candidate wheel: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r2/reviews_into_fixes-0.1.0-py3-none-any.whl`.
SHA-256: `5377e014422ac328ad604bedc5ae2f2431701aa8242d8b67145d9c989f0e7593`.

Build/install commands:

```bash
python3 -m pip wheel --no-index --no-build-isolation --no-deps --wheel-dir /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r2 .
python3 -m venv /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r2/install
/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r2/install/bin/python -I -m pip install --no-index --no-deps --no-cache-dir /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r2/reviews_into_fixes-0.1.0-py3-none-any.whl
```

Installed tests ran separately from the candidate directory using:

```text
pytest.main(["-q", "-p", "no:cacheprovider", "/home/yaron/projects/bright-data-reviews-into-fixes/tests/test_resume_mapping_regressions.py", "--import-mode=importlib", "--tb=short"])
pytest.main(["-q", "-p", "no:cacheprovider", "/home/yaron/projects/bright-data-reviews-into-fixes/tests", "--import-mode=importlib", "--tb=short"])
```

Other R2 checks:

- Source and installed-package compilation: exit 0, no output.
- Clean installed `pip check`: `No broken requirements found.`
- Console and module CLI version: `reviews-into-fixes 0.1.0`.
- Installed offline demo: three cards, `status: ok`, `decision: investigation_candidates`, zero requests.
- Golden comparison: no diff, exit 0. Original fixture bytes/hashes remain unchanged.
- Installed CLI variations: 9 of 9 PASS (versions, dry-run, planning, live refusal, collision, invalid analysis, missing resume gates, offline import); unintended outputs absent.
- Source and installed application/metadata TruffleHog scans: zero verified and zero unverified findings, exit 0. Verification and updates disabled.
- Wheel and source/test/fixture binding: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r2/SHA256SUMS` and `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0-r2/SOURCE_SHA256SUMS`.
- Historical R2 status: original candidate retained intact for comparison; the pointer was R2 at that time. No live calls, remote, stage, commit, push, or publication in that pass. R3 and the current release approvals supersede that candidate and its pending review gate. Live Web Unlocker remains disabled; provider live behavior is unverified.

## TDD Evidence

The expanded regression suite was written before implementation changes. Initial red run:

```text
17 failed, 39 passed in 0.64s
```

The failures covered sentence-local suppression, exact record identity, conflict status/counts, hit-centered excerpts, strict provider fields, timeout state, resume validation, live dry-run validation, transactional output, safe errors, and visible matched issue IDs.

The security expansion was also test-first. Its initial red run was:

```text
27 failed, 86 passed in 1.70s
```

Those failures covered production clock isolation, approval replay/lifetime/types, cumulative retention, provider URL mapping, fail-closed Web Unlocker scope, pending-error distinction, bounded regular-file reads, complete Markdown inertness, and adversarial CSV prefixes.

The brand review changes were also locked by tests first:

```text
17 failed, 108 passed in 0.86s
```

Those failures covered dual Web Unlocker response shapes, neutral local receipt states, unknown provider completeness, card/CSV provenance, mixed synthetic disclosure, README terminology, and brand-neutral distribution metadata.

The QA post-request output-write regression was added before the recovery implementation and initially failed because stderr had no `recovery_path`:

```text
1 failed; expected durable recovery metadata, observed KeyError('recovery_path')
```

The latest security regressions initially failed for Amazon query-bearing targets and missing bidi sanitation:

```text
2 failed; Amazon query targets reached approval/transport
4 failed; bidi controls remained in CSV cells and could precede formula prefixes
```

Resume retention-cap regression was added before its check: a pending receipt with one already-retained page and a one-record new approval must fail before request or nonce consumption.

Frozen-scope resume failure regressions were written before the correction:

```text
$ python3 -m pytest -q tests/test_resume_failures.py --tb=short
13 failed in 0.39s
```

They demonstrated incorrect zero-request reporting and lost receipts for snapshot GET timeouts, transport errors, HTTP errors, malformed JSON/arrays, pending responses, and requested-output failures. All 13 now pass through the real CLI with injected transports. They assert one GET, cumulative request count, per-invocation request count, prior sources, snapshot/job identifiers, safe errors, private saved libraries, failure of recovery storage, and a later explicit resume with a new approval (no retrigger).

Previous candidate local result (superseded by R2 above):

```text
$ python3 -m pytest -q
163 passed in 0.88s

$ python3 -m pytest -q tests/test_resume_failures.py tests/test_cli_contract.py
23 passed in 0.41s

$ python3 -m pytest -q tests/test_security_contract.py -k 'approval_marker or approval_nonce or unsafe_state_directory or symlinked_state_directory or wrong_owner_metadata or concurrent_processes or symlinked_consumption or symlinked_marker or tampered_marker or default_approval_state or state_home_symlink or cli_collection_consumes or cli_output_collision'
13 passed, 37 deselected in 0.13s

$ python3 -m compileall -q reviews_into_fixes
(no output; exit 0)
```

The full suite was also run against the INSTALLED wheel, not the repository package, from the candidate directory:

```bash
PYTHONPATH="/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/install/lib/python3.12/site-packages" python3 -c 'import reviews_into_fixes, pytest; assert "/dist/release-candidate-0.1.0/install/" in reviews_into_fixes.__file__, reviews_into_fixes.__file__; print("Testing installed candidate:", reviews_into_fixes.__file__); raise SystemExit(pytest.main(["-q", "/home/yaron/projects/bright-data-reviews-into-fixes/tests", "--import-mode=importlib"]))'
```

```text
Testing installed candidate: /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/install/lib/python3.12/site-packages/reviews_into_fixes/__init__.py
163 passed in 0.89s
```

The collection-output failure regressions inject a successful recording provider response, force the requested output write to fail, and verify either a private mode-0600 recovery library exists with source/job IDs, `requests_made: 1`, a stable recovery ID, and one transport call only, or that the structured fallback error still reports the actual request count and source/job IDs when recovery storage also fails.

The governing oracle is the build contract plus RF01-RF10 and applicable C01-C20 tests, not this prose file.

## CLI And Artifacts

```text
$ /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/install/bin/reviews-into-fixes analyze /home/yaron/projects/bright-data-reviews-into-fixes/fixtures/demo.json --out-dir /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/demo
{"card_count": 3, "decision": "investigation_candidates", "out_dir": "/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/demo", "requests_made": 0, "status": "ok"}

$ diff -ru /home/yaron/projects/bright-data-reviews-into-fixes/fixtures/expected /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/demo
(no output; exit 0)

$ python3 -m reviews_into_fixes collect fixtures/manifest.json --out /tmp/rif-review-never.json --live --dry-run
{"code": "invalid_input", "message": "live target is not allowed", "requests_made": 0}
(exit 2; no output file)
```

Offline import retained one invented record, omitted supplied person/profile fields, and reported `requests_made: 0`.

Installed CLI variations were captured and exit codes asserted:

- Analysis dry-run: exit 0, `card_count: 3`, `source_count: 5`, `requests_made: 0`, no output directory.
- Disabled/fixture live Web dry-run: exit 2, fixed `live target is not allowed`, zero requests, no output.
- Existing artifact collision: exit 2, fixed input error, zero requests, existing files unchanged.
- Invented provider import: exit 0, `status: processed`, `retained_records: 1`, zero requests.

## Historical Build And Install

- Build backend: setuptools 81.0.0.
- Distribution: `reviews-into-fixes`.
- Wheel: `reviews_into_fixes-0.1.0-py3-none-any.whl`.
- Candidate wheel: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/reviews_into_fixes-0.1.0-py3-none-any.whl`.
- Wheel SHA-256: `c1fa2eebf3bc782a171f47817da1fd2c620f800a8a6ccab29143756b8d58275e`.
- Build command: `python3 -m pip wheel --no-index --no-build-isolation --no-deps --wheel-dir /home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0 .`.
- Clean installation used `pip install --no-index` into `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/install`.
- Wheel checksum: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/SHA256SUMS`.
- Source/test/README/fixture binding: `/home/yaron/projects/bright-data-reviews-into-fixes/dist/release-candidate-0.1.0/SOURCE_SHA256SUMS` (verify from repository root with `sha256sum -c`).
- Installed CLI returned `reviews-into-fixes 0.1.0`.
- Installed CLI demo matched all checked fixtures byte-for-byte.
- Clean-environment `python -m pip check`: `No broken requirements found.`
- Local interpreter: Python 3.12.3. Python 3.11 is configured in CI but was not available for a local run.

## Security Scan

```text
trufflehog filesystem . --no-verification --no-update --fail --json --exclude-paths .trufflehog-exclude.txt
verified_secrets=0, unverified_secrets=0
```

Generated caches, build output, distribution metadata, and `.git` are excluded by the checked scanner exclusion file. A separate fixed-pattern scan also returned no private-key, provider-token, GitHub-token, AWS-key, or literal bearer-secret matches.

## Scope

- Offline analysis and exports: verified with invented fixtures.
- Module and console entry points: verified locally.
- Provider adapters: verified only with injected fake transports and invented responses.
- Live Bright Data account/API behavior: not tested and not claimed verified.
- Live Web Unlocker remains disabled; both documented response shapes are parser-tested offline.
- Suggested investigation checks: not validated as defects or guaranteed runnable procedures.

## Publication Gate

The original frozen passes performed no live call, remote creation, commit, or push and awaited focused review. Those pending approval notes are historical: the current core SHIP and skill approvals are recorded above, and the user now explicitly authorizes this public showcase. Publication still requires the actual intended staged inventory, successful normal hooks, pushed/public HEAD verification, unauthenticated clone checks, and the existing Python 3.11/3.12 CI. No further feature design or test matrix is part of this release.
