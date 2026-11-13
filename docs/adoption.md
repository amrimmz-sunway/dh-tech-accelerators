# Measuring adoption

Accelerators that generate files (`pipeline-gen`, `stack-scaffold`) put one marker comment at the top of every new file:

```
generated-by: dh-tech-accelerators/<plugin>@<version>
```

Nothing is sent anywhere: there's no telemetry. Adoption is counted from code that teams have actually merged.

## Count it

GitHub code search only indexes default branches, so this counts merged usage:

```bash
gh search code "generated-by: dh-tech-accelerators" --owner <org> --limit 200 \
  --json repository,path \
  --jq '.[] | [.repository.nameWithOwner, .path] | @tsv' | sort -u
```

Per plugin:

```bash
gh search code "dh-tech-accelerators/pipeline-gen" --owner <org> --json repository --jq '.[].repository.nameWithOwner' | sort -u
gh search code "dh-tech-accelerators/stack-scaffold" --owner <org> --json repository --jq '.[].repository.nameWithOwner' | sort -u
```

Map each repository to its owning squad with your team's own repo-to-squad list. Keep that list out of this repo while it is public.

## Limits

- Code search can lag a few hours behind a merge, and skips very large files and forks.
- People can delete the marker. Treat the count as a lower bound.
- Plugins that don't generate files (`pr-evidence`, `branch-split`) can't be counted this way. Use squad sign-off for those instead.
