# Design: pipeline-gen

## Purpose
Give repos without CI a GitHub Actions workflow that lints, tests and builds on every PR, fitted to the repo's real stack and scripts.

## Flow
1. `detect.py` reads the repo and prints stack JSON (stack, versions, package manager, scripts, warnings).
2. Claude confirms the stack and open options (Node version, branches, iOS, type check, SonarCloud) with the engineer.
3. `render.py` renders the workflow to stdout for review, then writes `.github/workflows/ci.yml`.
4. `validate.sh` parses the YAML, checks the guardrails and runs actionlint when installed.

## AI vs deterministic
| Claude | Scripts |
|---|---|
| Resolves ambiguous or missing inputs, checks the Node version against framework support, explains warnings and what will make the first run red | Stack detection, templating, SHA pinning, guardrail validation |

## Never
Deploys, signs, uploads to a store, pushes images, runs Terraform, commits, pushes, overwrites an existing workflow without a yes, invents lint or test commands, or embeds secrets.

## Risks
| Risk | Mitigation |
|---|---|
| Supply-chain attack through a moved action tag | Every action pinned to a full commit SHA from `pins.json`; bump process in `references/action-pins.md` |
| Workflow token abused | `permissions: contents: read`; no deploy or write steps; `validate.sh` fails on `write` permissions |
| Secrets in the workflow | Only `SONAR_TOKEN` from repo secrets in the opt-in job; validator guardrails |
| Overwriting a team's existing CI | Existing workflows are read and shown first; overwrite needs `--force` after an explicit yes |
| Invented commands make CI meaningless or red | Steps appear only when the script exists in `package.json` |
| Runner cost (macOS ~10x) | iOS build is opt-in |
| `detect.py` drifts from the copy in stack-scaffold | `scripts/check.sh` fails CI if the two copies differ |
| Prompt injection through READMEs or package scripts | Treated as data and reported |
