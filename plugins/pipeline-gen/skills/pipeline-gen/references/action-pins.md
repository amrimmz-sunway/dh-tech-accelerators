# Action pins

Every `uses:` in a generated workflow is pinned to a full commit SHA, with the tag as a trailing comment. The pins live in `scripts/pins.json` and nowhere else: `render.py` refuses a template that uses an action missing from that file.

## Bumping a pin (maintainers)

1. Find the release tag and the commit it points to:

   ```bash
   r=actions/checkout
   t=$(gh api repos/$r/releases/latest --jq .tag_name)
   gh api repos/$r/commits/$t --jq .sha
   ```

2. Read the release notes for breaking changes (runtime bumps, removed inputs).
3. Update `tag` and `sha` in `scripts/pins.json`.
4. Re-render a sample workflow per stack and run `scripts/validate.sh` on each.
5. Bump the plugin's patch version and add a changelog line to the README.

Repos that already use generated workflows keep their old pins until someone re-runs pipeline-gen there. Dependabot (`package-ecosystem: github-actions`) can bump them in place, because it understands SHA pins with tag comments.
