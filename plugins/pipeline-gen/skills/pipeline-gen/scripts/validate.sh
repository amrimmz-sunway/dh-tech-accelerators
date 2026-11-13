#!/usr/bin/env bash
# Validate a generated workflow. Read-only.
# Usage: validate.sh <workflow.yml>
# Exit: 0 pass, 1 a check failed, 2 usage, 3 no YAML parser available.
set -u

f="${1:-}"
if [ -z "$f" ] || [ "$f" = "-h" ] || [ "$f" = "--help" ]; then
  echo "usage: validate.sh <workflow.yml>" >&2; exit 2
fi
[ -f "$f" ] || { echo "not a file: $f" >&2; exit 2; }

fail=0
ok()   { echo "PASS  $*"; }
bad()  { echo "FAIL  $*"; fail=1; }
warn() { echo "WARN  $*"; }

# 1. YAML parses
if command -v ruby >/dev/null 2>&1; then
  if err=$(ruby -ryaml -e 'YAML.safe_load(File.read(ARGV[0]), aliases: false)' "$f" 2>&1); then
    ok "YAML parses"
  else
    bad "YAML does not parse: $err"
  fi
elif command -v python3 >/dev/null 2>&1 && python3 -c 'import yaml' 2>/dev/null; then
  if python3 -c 'import sys,yaml; yaml.safe_load(open(sys.argv[1]))' "$f"; then ok "YAML parses"; else bad "YAML does not parse"; fi
else
  echo "no YAML parser: install ruby or python3 with PyYAML (or actionlint)" >&2; exit 3
fi

# 2. Guardrails
grep -q '^# generated-by: dh-tech-accelerators/pipeline-gen@' "$f" && ok "adoption marker present" || bad "adoption marker missing on line 1"
grep -q '^permissions:' "$f" && ok "top-level permissions set" || bad "no top-level permissions block"
grep -Eq '^\s+(contents|packages|id-token|actions|pull-requests|checks|deployments|issues|statuses): *write' "$f" \
  && bad "a write permission is granted (CI-only workflows need read)" || ok "no write permissions"

unpinned=$(grep -E '^\s*-?\s*uses:' "$f" | grep -Ev 'uses: *[^@ ]+@[0-9a-f]{40}( |$)' || true)
if [ -n "$unpinned" ]; then bad "actions not pinned to a full commit SHA:"; echo "$unpinned" | sed 's/^/        /'; else ok "every action pinned to a commit SHA"; fi

grep -Eiq '(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*["'"'"']?[A-Za-z0-9/+_-]{12,}' "$f" \
  && bad "looks like a literal credential; use \${{ secrets.NAME }}" || ok "no literal credentials"

grep -Eq '(docker push|kubectl|terraform (apply|destroy)|fastlane|gcloud|aws |az |hcloud|codesign|altool|upload-artifact)' "$f" \
  && warn "deploy/signing/upload command found: v1 is CI-only, confirm this was intended" || ok "no deploy, signing or upload steps"

# 3. actionlint (optional but recommended)
if command -v actionlint >/dev/null 2>&1; then
  if actionlint -no-color "$f"; then ok "actionlint clean"; else bad "actionlint reported problems (above)"; fi
else
  warn "actionlint not installed, schema/expression checks skipped (brew install actionlint)"
fi

exit $fail
