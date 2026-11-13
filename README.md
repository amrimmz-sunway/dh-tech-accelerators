# DH Tech Accelerators

A Claude Code plugin marketplace for **Sunway DH** that provides reusable, AI-assisted engineering accelerators. Each plugin is standalone, so you only install the ones you need.

| Plugin | What it does |
|---|---|
| [`pr-evidence`](plugins/pr-evidence/README.md) | Read-only peer-review and CI-check evidence report for your own merged PRs |
| [`branch-split`](plugins/branch-split/README.md) | Split one pile of uncommitted work into per-ticket branches, with verified patches, an apply script you run, and the PR order |
| [`pipeline-gen`](plugins/pipeline-gen/README.md) | Add a CI-only GitHub Actions workflow (lint, test, build) fitted to the repo's stack: Node/Express, Angular/Ionic, React Native, .NET Framework |
| [`stack-scaffold`](plugins/stack-scaffold/README.md) | Scaffold a new endpoint, screen, page or controller that copies the repo's own conventions, across the same four stacks |

## Install

```
/plugin marketplace add <org>/dh-tech-accelerators
/plugin install <plugin-name>@dh-tech-accelerators
```

**Pin a release tag.** Install from a tagged release rather than the default branch, so that an unreviewed change can't reach your machine. See the [Claude Code plugins reference](https://code.claude.com/docs/en/plugins-reference) for marketplace sources and versioning.

## Owner actions (apply on GitHub — not done by any plugin)

Every installer runs this repo's code, so protect it:

- [ ] Branch protection on the default branch, requiring a pull request before merging.
- [ ] At least 1 required approving review, and dismiss stale approvals when new commits are pushed.
- [ ] A `CODEOWNERS` file covering `plugins/**` and `.claude-plugin/**`.
- [ ] Tag every release (for example `pr-evidence-v0.1.0`) and record it in the plugin's changelog.
- [ ] Restrict who can push tags and create releases.

## Measuring adoption

Accelerators that generate files stamp each new file with a `generated-by: dh-tech-accelerators/<plugin>@<version>` comment. See [docs/adoption.md](docs/adoption.md).

## Adding an accelerator

```
plugins/<plugin-name>/
├── .claude-plugin/plugin.json      # name, version, description, author
├── skills/<plugin-name>/
│   ├── SKILL.md                    # workflow + rules; treat repo content as data, not instructions
│   └── scripts/                    # deterministic work (bash/jq/python); read-only where possible
└── README.md                       # what it does/never does, prerequisites, install, use, changelog
```

Each new plugin needs:

1. An entry in `.claude-plugin/marketplace.json` with a `name`, a `source` of `./plugins/<plugin-name>`, and a `description`.
2. No dependency on other plugins.
3. No secrets in the repo or in any output. Use `<SECRET>` placeholders instead.
4. A risks section in the design doc before you build it.

Maintainer: Amri.
