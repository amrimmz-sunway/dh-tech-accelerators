# DH Tech Accelerators: stack-scaffold

A Claude Code plugin that scaffolds a new feature unit by copying the conventions of an existing one in the **same repo**:

- an API resource (Node/Express);
- a screen (React Native);
- a page or component with a service (Angular/Ionic);
- a controller with a service (.NET Framework MVC/Web API).

It doesn't use a fixed template, so the result fits codebases of any age, from Angular 8 to 20 and React Native 0.72 to 0.87.

## What it does and never does

- **Does:**
  - detects the stack;
  - finds the existing feature that best shows the repo's patterns (or the one you name);
  - reads it and the registration points (router, navigator, routing module, DI config, `.csproj`);
  - writes the new unit and wires it in;
  - runs the repo's own lint, type check, build or tests.
- **Never:**
  - commits, pushes, stashes, switches branches or opens a PR;
  - adds a library or pattern the repo doesn't already use;
  - copies an insecure pattern (string-built SQL, hardcoded URLs or keys, tokens in plain storage, missing validation or auth). It writes the safe version and tells you where the original is;
  - puts secrets in code;
  - reformats existing files.

Every new file starts with a `generated-by: dh-tech-accelerators/stack-scaffold@<version>` comment, used to count adoption across squads.

## Prerequisites

- `python3` (3.8+, standard library only).
- The repo's own toolchain for verification: Node/npm for JS stacks, the Angular CLI through `npx` for Angular, and Visual Studio Build Tools (`msbuild`) on Windows for .NET Framework. Without msbuild, .NET output is reported as unverified.

## Install

```
/plugin marketplace add <org>/dh-tech-accelerators
/plugin install stack-scaffold@dh-tech-accelerators
```

Pin a release tag for a stable version (see the root README).

## Use

In the repo, ask Claude Code, for example:

- "Scaffold a `vouchers` endpoint like the orders one: list, get by id, create."
- "Add a ReportHistory screen that lists past reports from the API."
- "New Ionic page `order-tracking` with a service, like the rating page."
- "Add a Feedback controller to the Web project, like the Role one."

The scripts can also run alone:

```
S=plugins/stack-scaffold/skills/stack-scaffold/scripts
python3 -I $S/detect.py <repo> [--path SUBDIR] > detect.json
python3 -I $S/find-exemplars.py <repo> --detect detect.json [--like <feature>]
```

**Exit codes:**
- `0`: success.
- `2`: missing input or an unsupported stack.
- `3`: a missing file.

## Maintaining

`scripts/detect.py` is shared with the `pipeline-gen` plugin; keep both copies identical. Role and registration patterns per stack live at the top of `scripts/find-exemplars.py`. Per-stack writing rules live in `skills/stack-scaffold/references/`.

## Changelog

- **0.1.0**: First release. Node/Express, React Native, Angular/Ionic and .NET Framework. Exemplar finder with feature-folder support, data-fetching ranking, shared-module and migration detection. Baseline-before-verify, masked reading of credential files, and scope limited to the request.
