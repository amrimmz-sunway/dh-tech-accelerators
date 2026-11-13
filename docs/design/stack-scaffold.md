# Design: stack-scaffold

## Purpose
Add a new feature unit (endpoint, screen, page or controller) that copies the conventions of an existing unit in the same repo, so it fits codebases of any age without a fixed template.

## Flow
1. `detect.py` detects the stack.
2. Claude asks what to create; `find-exemplars.py` ranks existing units and finds registration points.
3. Claude picks the exemplar by shape, reads it plus the per-stack reference, and checks the request against the code (fields, endpoint, schema, test pickup, entry point).
4. Claude shows a plan, records a lint/test/build baseline, writes the files, then re-runs verification and reports before → after.

## AI vs deterministic
| Claude | Scripts |
|---|---|
| Exemplar choice, writing the new code in the repo's style, spotting and refusing insecure patterns, planning, baseline comparison | Stack detection, exemplar ranking, registration-file and migration discovery |

## Never
Commits, pushes, stashes or switches branches; adds a library or pattern the repo doesn't use; copies a vulnerability; puts secrets in code; reformats existing files.

## Risks
| Risk | Mitigation |
|---|---|
| Copies an insecure pattern (string-built SQL, hardcoded keys, plain token storage) | Rule to write the safe version and report the original's file and line |
| Reads and exposes plaintext credentials in config files | Credential files are never read whole; shape learned with a masked grep; values never printed |
| Breaks the build or hides new failures among old ones | Baseline before writing; pass = no new errors; unverifiable runs reported as unverified |
| Scope creep (copies every endpoint of the exemplar) | Scope limited to the request; omissions listed |
| Silent assumptions about fields or endpoints | Step 5 checks against the model/API and lists assumptions |
| Adoption can't be measured | `generated-by` marker on each new file; see [adoption.md](../adoption.md) |
| `detect.py` drifts from the copy in pipeline-gen | `scripts/check.sh` fails CI if the two copies differ |
| Prompt injection through code comments | Treated as data and reported |
