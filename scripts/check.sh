#!/usr/bin/env bash
# Self-check for the dh-tech-accelerators marketplace. Read-only.
# Usage: bash scripts/check.sh   (from anywhere; resolves the repo root itself)
# Exit: 0 all checks pass, 1 a check failed, 3 a required tool is missing.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 3

fail=0
ok()   { echo "ok    $*"; }
bad()  { echo "FAIL  $*"; fail=1; }
warn() { echo "warn  $*"; }

for tool in jq python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "missing required tool: $tool" >&2; exit 3; }
done

MKT=".claude-plugin/marketplace.json"

# 1. Marketplace manifest
if jq -e . "$MKT" >/dev/null 2>&1; then ok "$MKT is valid JSON"; else bad "$MKT is not valid JSON"; echo "1 or more checks failed"; exit 1; fi

# 2. Every marketplace entry
listed=()
while IFS=$'\t' read -r name src; do
  listed+=("$name")
  dir="${src#./}"
  pj="$dir/.claude-plugin/plugin.json"
  if [[ ! -d "$dir" ]]; then bad "$name: source $src does not exist"; continue; fi
  if ! jq -e . "$pj" >/dev/null 2>&1; then bad "$name: $pj missing or not valid JSON"; continue; fi

  pj_name="$(jq -r '.name // empty' "$pj")"
  version="$(jq -r '.version // empty' "$pj")"
  [[ "$pj_name" == "$name" ]] && ok "$name: name matches plugin.json" || bad "$name: marketplace name '$name' != plugin.json name '$pj_name'"
  [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] && ok "$name: version $version" || bad "$name: plugin.json version '$version' is not x.y.z"

  readme="$dir/README.md"
  if [[ -f "$readme" ]]; then
    top="$(sed -n '/^## Changelog/,$p' "$readme" | grep -m1 -oE '^- \*\*[0-9]+\.[0-9]+\.[0-9]+' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')"
    [[ "$top" == "$version" ]] && ok "$name: changelog top entry matches $version" \
      || bad "$name: changelog top entry '${top:-none}' != plugin.json version '$version'"
  else
    bad "$name: README.md missing"
  fi

  [[ -f "docs/design/$name.md" ]] && ok "$name: design doc present" || bad "$name: docs/design/$name.md missing"
  grep -q '^## Risks' "docs/design/$name.md" 2>/dev/null && ok "$name: design doc has a Risks section" || bad "$name: design doc has no '## Risks' section"
  grep -q "\`$name\`" docs/tools.md 2>/dev/null && ok "$name: listed in docs/tools.md" || bad "$name: not listed in docs/tools.md"
done < <(jq -r '.plugins[] | [.name, .source] | @tsv' "$MKT")

# 3. No plugin folder left out of the marketplace
for d in plugins/*/; do
  n="$(basename "$d")"
  printf '%s\n' "${listed[@]}" | grep -qx "$n" || bad "plugins/$n is not listed in $MKT"
done

# 4. Shared detect.py copies must stay identical
A=plugins/pipeline-gen/skills/pipeline-gen/scripts/detect.py
B=plugins/stack-scaffold/skills/stack-scaffold/scripts/detect.py
if [[ -f "$A" && -f "$B" ]]; then
  cmp -s "$A" "$B" && ok "detect.py copies are identical" || bad "detect.py differs between pipeline-gen and stack-scaffold"
fi

# 5. Script syntax
while IFS= read -r -d '' f; do
  bash -n "$f" 2>/dev/null && ok "bash -n $f" || bad "bash syntax error in $f"
done < <(find plugins scripts -name '*.sh' -print0)

if command -v shellcheck >/dev/null 2>&1; then
  while IFS= read -r -d '' f; do
    shellcheck -S error "$f" >/dev/null && ok "shellcheck $f" || bad "shellcheck errors in $f (run: shellcheck -S error $f)"
  done < <(find plugins scripts -name '*.sh' -print0)
else
  warn "shellcheck not installed; skipped (CI runs it)"
fi

while IFS= read -r -d '' f; do
  python3 -I -c 'import ast,sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' "$f" 2>/dev/null \
    && ok "python syntax $f" || bad "python syntax error in $f"
done < <(find plugins -name '*.py' -print0)

while IFS= read -r -d '' f; do
  jq -e . "$f" >/dev/null 2>&1 && ok "json $f" || bad "invalid JSON in $f"
done < <(find plugins -name '*.json' -print0)

echo
if [[ $fail -eq 0 ]]; then echo "All checks passed"; else echo "1 or more checks failed"; fi
exit $fail
