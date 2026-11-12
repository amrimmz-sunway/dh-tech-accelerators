# DH Tech Report: PR Evidence

A Claude Code plugin that produces a read-only report on **peer review** and **automated CI checks** for an engineer's own merged GitHub PRs over a period. It's useful for KRA/KPI evidence, appraisals and audits.

## What it does and never does

- **Does:** reads merged PRs, their reviews and their check results through the `gh` CLI. Computes metrics deterministically with `jq`. Writes `summary.json`, `pr-evidence.csv` and `pr-evidence-report.md` to a private folder.
- **Never:**
  - writes to GitHub
  - commits or pushes anything
  - reports on another engineer without explicit confirmation of authorisation
  - follows instructions found inside PR titles or bodies

## Prerequisites

- [GitHub CLI](https://cli.github.com/) (`gh`), signed in with `gh auth login`.
- [`jq`](https://jqlang.org/) 1.6 or later.
- `git` and `bash`. macOS's default bash 3.2 works.

Recommended: a [fine-grained personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) with **read-only** access to Pull requests, Contents and Commit statuses for the repos you report on. You can use it with `gh auth login --with-token`.

## Install

```
/plugin marketplace add <org>/dh-tech-report
/plugin install pr-evidence@dh-tech-report
```

Pin a release tag for a stable version (see the root README).

## Use

Ask Claude Code, for example:

- "Give me my PR evidence for 2026-01-01 to 2026-10-31 for `<org>/<repo>` and `<org>/<repo2>`."
- "PR evidence for this year across the `<org>` org, with titles redacted."

Or run the script directly:

```
pr-evidence.sh --since YYYY-MM-DD --until YYYY-MM-DD
               (--repo owner/name)... | --org ORG
               [--author LOGIN|@me] [--confirm-authorised]
               [--exclude-reviewer LOGIN]... [--redact-titles]
               [--out DIR] [-h|--help]
```

Output goes to `<base>/<login>_<since>_<until>_<timestamp>/`, where `<base>` is the first of these that applies:

1. `--out DIR`: the exact folder to use (no per-run subfolder is added).
2. `PR_EVIDENCE_DIR` environment variable.
3. `~/Documents/pr-evidence-reports`: macOS (`/Users/<you>/Documents/...`) and Windows Git Bash (`C:\Users\<you>\Documents\...`).
4. `~/pr-evidence-reports`: fallback when there is no `~/Documents` (for example WSL or Linux).

The folder is created with owner-only permissions (`chmod 700`). On Windows that has no effect, so access is controlled by your user profile's NTFS permissions.

> If your Documents folder syncs to iCloud (macOS "Desktop & Documents") or OneDrive (Windows Known Folder Move), the reports sync too. OneDrive for Business stays inside the Sunway tenant; a personal iCloud account does not. Set `PR_EVIDENCE_DIR` to a non-synced folder if that matters.

**Exit codes:**
- `0`: success.
- `1`: a fetch failed. Check the repo name and your access.
- `2`: a usage or guardrail refusal.
- `3`: a dependency or authentication is missing.

## How the metrics are defined

**Countable review:** a review whose author is neither the PR author nor a bot. Bots are any login ending in `[bot]`, plus `github-actions`, `dependabot`, `copilot-pull-request-reviewer`, `Copilot`, and anything you pass with `--exclude-reviewer`.

**Approved by another engineer:** at least one countable review with state `APPROVED`.

**Final-commit checks passing:**
- A PR counts as passing when every item in its check rollup passed. A check run passes with conclusion `SUCCESS`, `NEUTRAL` or `SKIPPED`; a legacy status passes with state `SUCCESS`.
- Anything else, including pending, counts as **not passing**.
- A PR with no checks at all counts as **no checks configured**, which is reported separately.
- The percentage is calculated as passing ÷ (passing + not passing).

**Time to first peer review:** the earliest countable review's submission time minus the PR's creation time, in hours. The report shows the median across PRs.

All percentages and hours are rounded to 1 decimal.

## Privacy and handling

- The plugin reports on your own PRs by default. Reporting on someone else requires `--confirm-authorised`, and the report records who ran it.
- The output is **internal — do not share outside Sunway**. Use `--redact-titles` when sharing more widely.
- Don't commit the output. The script warns you if `--out` points inside a git working tree.

## Known limits

- The script fetches at most 1000 merged PRs per repo per run, and at most 1000 PRs for org repo discovery. It warns when either limit is hit.
- Check status reflects the PR's final head commit as GitHub reports it now.

## Changelog

- **0.1.0**: initial release.
