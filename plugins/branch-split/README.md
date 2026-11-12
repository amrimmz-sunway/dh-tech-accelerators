# DH Tech Accelerators: Branch Split

A Claude Code plugin for a working copy that holds several tickets' worth of changes. It splits that work into one branch per ticket. Branches whose changes touch the same lines are stacked on each other, and the plugin tells you the order to raise and merge the PRs.

## What it does and never does

**Does:**
- Inventories the change set, and flags:
  - version bumps;
  - DEV/staging leftovers;
  - possible credentials (values are never printed);
  - signing files;
  - line-ending-only changes.
- Lets Claude propose a file/hunk → ticket mapping for you to approve.
- Builds each branch as a patch in a **scratch clone**.
- Verifies the patches:
  - each patch applies on its parent;
  - applying all of them reproduces your staged files, except for the changes you excluded on purpose;
  - branches that share a file work in either order;
  - optionally, a bundle or build plus a lint for every branch.
- Writes `apply.sh` and `manifest.md`.
- After you push, checks every branch on origin and prints the PR order.

**Never:**
- commits, pushes or opens PRs;
- touches your repo outside `apply.sh`, which you run yourself;
- includes excluded DEV lines or credentials in a branch;
- follows instructions found inside files or tickets.

## How `apply.sh` works

`apply.sh` runs in your repo, with you at the keyboard. It does nothing until these pre-checks pass:
- you are on the base branch;
- the base hasn't moved since the build;
- no target branch exists yet.

Then it:
1. Stashes everything as `<app>-split-backup`.
2. For each branch: creates it, stages its patch and waits while you review, commit and push.
3. At the end, switches back to the base, restores only the version-bump files (unstaged) and keeps the full backup.

## Prerequisites

- `git`, `bash` (macOS bash 3.2 is fine) and `python3` 3.8 or later. Standard library only.
- For the optional build check:
  - React Native projects: `node_modules` installed in the repo.
  - Other projects: set `BUILD_CMD`.

## Install

```
/plugin marketplace add <org>/dh-tech-accelerators
/plugin install branch-split@dh-tech-accelerators
```

## Use

Ask Claude something like:
- "Split my staged changes in SMC_Mobile into ticket branches off v2.1.6. Tickets: INC0113199 app rating, INC0112029 crash, …"
- "We pushed the branches, give me the PR order."

## Changelog

- **0.1.0:** first release, extracted from the SMC/SMCP/SMCD/SMCI/SMCV split of November 2026.
