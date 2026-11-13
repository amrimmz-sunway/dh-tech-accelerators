# DH Tech Accelerators: pipeline-gen

A Claude Code plugin that adds a **CI-only GitHub Actions workflow** to a repo. It lints, tests and builds on every pull request, fitted to the repo's real stack and `package.json` scripts.

## What it does and never does

- **Does:**
  - detects the stack (Node/Express, Angular, Ionic/Angular, React Native, .NET Framework);
  - confirms the Node version, branches and options with you;
  - writes `.github/workflows/ci.yml` and validates it.
- **Every generated workflow has:**
  - actions pinned to full commit SHAs;
  - `permissions: contents: read`;
  - cancel-in-progress concurrency;
  - dependency caching;
  - a `generated-by` marker on line 1 (used to count adoption).
- **Never:**
  - deploys, signs, uploads to a store, pushes images, or runs Terraform;
  - commits, pushes or opens a PR;
  - overwrites an existing workflow without your explicit yes;
  - invents test or lint commands that your repo doesn't have;
  - puts secrets in the workflow (the opt-in SonarCloud job reads `SONAR_TOKEN` from repo secrets).

## Prerequisites

- `python3` (3.8+, standard library only) and `bash`.
- `ruby` (preinstalled on most Macs) or Python with PyYAML, for the YAML check.
- Recommended: [`actionlint`](https://github.com/rhysd/actionlint) (`brew install actionlint`) for full schema and expression checks.

## Install

```
/plugin marketplace add <org>/dh-tech-accelerators
/plugin install pipeline-gen@dh-tech-accelerators
```

Pin a release tag for a stable version (see the root README).

## Use

In the repo, ask Claude Code, for example:

- "Add CI to this repo."
- "Generate a GitHub Actions pipeline for the API in `src/api`."
- "Set up CI for this React Native app, including an iOS build."

Or run the scripts directly:

```
S=plugins/pipeline-gen/skills/pipeline-gen/scripts
python3 -I $S/detect.py <repo> [--path SUBDIR] > detect.json
python3 -I $S/render.py --repo <repo> --detect detect.json \
    [--node-version 22] [--branches main,develop] [--ios] [--typecheck] \
    [--sonar] [--no-android] [--no-audit] [--out .github/workflows/ci.yml] [--force] [--stdout]
bash $S/validate.sh <repo>/.github/workflows/ci.yml
```

**Exit codes:**
- `0`: success.
- `1`: a validation check failed.
- `2`: missing input or a refused action.
- `3`: a missing file or tool.

## What usually makes the first run red

Detection reports these as `warnings`:

- **No Node version in the repo.** You'll be asked; match production. See `skills/pipeline-gen/references/runtime-compat.md`.
- **React Native: `google-services.json` not committed.** The Android build fails until CI gets that file. That's out of scope for v1, since it needs secrets.
- **.NET Framework projects below 4.6.2.** GitHub's Windows runners don't ship those targeting packs. Retarget the project, or add the `Microsoft.NETFramework.ReferenceAssemblies` NuGet package.
- **Test suites that need a database or network.** CI runs them as-is. Mark integration tests, or give them their own script.

## Maintaining

Action pins live in `skills/pipeline-gen/scripts/pins.json`; see `references/action-pins.md` to bump them. `detect.py` is shared with the `stack-scaffold` plugin; keep both copies identical.

## Changelog

- **0.1.0**: First release. Node/Express, Angular, Ionic/Angular, React Native (Android, optional iOS) and .NET Framework templates. Optional SonarCloud job. Validator with guardrails.
