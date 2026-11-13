# Tool inventory

Every AI-powered tool the team builds and maintains. Each one is a Claude Code plugin: Claude handles the judgement steps (reading code, choosing, writing narrative or code), and the bundled scripts do the deterministic steps (fetching, computing, checking).

Release tags follow `<plugin>-v<version>`. Each tag links to its GitHub Release; dates are MYT.

## In this marketplace

| Tool | Author | Version | Release tag | What Claude does | What the scripts do | Design | Changelog |
|---|---|---|---|---|---|---|---|
| `pr-evidence` | Amri | 0.2.0 | [`pr-evidence-v0.2.0`](https://github.com/amrimmz-sunway/dh-tech-accelerators/releases/tag/pr-evidence-v0.2.0) (13 Nov 2026) | Gathers inputs, enforces the authorisation guardrail, writes the report narrative from the computed numbers | `pr-evidence.sh` fetches PRs, reviews and checks via `gh`; `metrics.jq` computes every metric | [design](design/pr-evidence.md) | [changelog](../plugins/pr-evidence/README.md#changelog) |
| `branch-split` | Amri | 0.1.0 | [`branch-split-v0.1.0`](https://github.com/amrimmz-sunway/dh-tech-accelerators/releases/tag/branch-split-v0.1.0) (13 Nov 2026) | Maps each file or hunk to a ticket, decides stacking, explains the PR order | `split.py` scans, builds patches in a scratch clone, verifies, renders `apply.sh`; `buildcheck.sh` builds and lints each branch | [design](design/branch-split.md) | [changelog](../plugins/branch-split/README.md#changelog) |
| `pipeline-gen` | Amri | 0.1.0 | [`pipeline-gen-v0.1.0`](https://github.com/amrimmz-sunway/dh-tech-accelerators/releases/tag/pipeline-gen-v0.1.0) (13 Nov 2026) | Confirms stack, Node version and options with the engineer, explains what will make the first run red | `detect.py` detects the stack; `render.py` renders a pinned workflow; `validate.sh` checks guardrails and runs actionlint | [design](design/pipeline-gen.md) | [changelog](../plugins/pipeline-gen/README.md#changelog) |
| `stack-scaffold` | Amri | 0.1.0 | [`stack-scaffold-v0.1.0`](https://github.com/amrimmz-sunway/dh-tech-accelerators/releases/tag/stack-scaffold-v0.1.0) (13 Nov 2026) | Picks the exemplar by shape, writes the new unit in the repo's own style, refuses to copy insecure patterns, verifies against a baseline | `detect.py` detects the stack; `find-exemplars.py` ranks exemplars and finds registration points | [design](design/stack-scaffold.md) | [changelog](../plugins/stack-scaffold/README.md#changelog) |

## Team tools in other repos

These are not listed in `marketplace.json`: installing from an unpinned external source would break the "pin a release tag" rule in the [root README](../README.md).

| Tool | Author | Source | Version | What it does |
|---|---|---|---|---|
| `sunmedgo-timesheet` (`/log-sunmedgo`) | Arif Faeetz Ruslee | `arifruslee/claude-mods`, `plugins/sunmedgo-timesheet` (commit `9b73ede`) | 0.3.0 | Matches SunMed GO 2.0 work to the right Jira space and ticket using the SG2 Confluence registry, then logs time after explicit approval |

## Adding a tool here

Add a row when a plugin ships its first release. Bump the version and tag columns on every release, in the same PR as the plugin's changelog entry. `scripts/check.sh` fails CI when a plugin's `plugin.json` version doesn't match the top entry of its changelog, or when its design doc is missing.
