# DH Tech Accelerators

A Claude Code plugin marketplace for **Sunway DH** that provides reusable, AI-assisted engineering accelerators. Each plugin is standalone, so you only install the ones you need.

| Plugin | What it does |
|---|---|
| [`pr-evidence`](plugins/pr-evidence/README.md) | Read-only peer-review and CI-check evidence report for your own merged PRs |
| [`branch-split`](plugins/branch-split/README.md) | Split one pile of uncommitted work into per-ticket branches, with verified patches, an apply script you run, and the PR order |
| [`pipeline-gen`](plugins/pipeline-gen/README.md) | Add a CI-only GitHub Actions workflow (lint, test, build) fitted to the repo's stack: Node/Express, Angular/Ionic, React Native, .NET Framework |
| [`stack-scaffold`](plugins/stack-scaffold/README.md) | Scaffold a new endpoint, screen, page or controller that copies the repo's own conventions, across the same four stacks |

The full inventory, including team tools that live in other repos, with authors, versions, release tags and design docs, is in [docs/tools.md](docs/tools.md).

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
- [x] A `CODEOWNERS` file covering `plugins/**` and `.claude-plugin/**` ([.github/CODEOWNERS](.github/CODEOWNERS)).
- [ ] Tag every release (for example `pr-evidence-v0.1.0`) and record it in the plugin's changelog.
- [ ] Restrict who can push tags and create releases.
- [ ] Make the `validate` workflow a required status check on the default branch.

## Releases

Tag each release as `<plugin>-v<version>`, matching the `version` in the plugin's `plugin.json` and the top entry of its README changelog. [`scripts/check.sh`](scripts/check.sh) runs on every PR (via `.github/workflows/validate.yml`) and fails when the manifest, versions, changelogs, design docs or script syntax are out of step. Run it locally with `bash scripts/check.sh` before opening a PR.

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
4. A design doc at `docs/design/<plugin-name>.md` with a `## Risks` section, written before you build it.
5. A row in [docs/tools.md](docs/tools.md) and a changelog entry for every version.

Maintainer: Amri.
