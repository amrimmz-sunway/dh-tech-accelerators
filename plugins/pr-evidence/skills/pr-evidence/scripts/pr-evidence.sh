#!/usr/bin/env bash
# pr-evidence.sh — read-only peer-review and CI-check evidence for merged GitHub PRs.
# Only calls: gh api user, gh search prs, gh pr list. Never writes to GitHub.
# Compatible with macOS default bash 3.2.
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
METRICS="$SCRIPT_DIR/metrics.jq"
LIMIT=1000
DEFAULT_BOTS=(github-actions dependabot copilot-pull-request-reviewer Copilot)
LABEL="Internal — do not share outside Sunway"
CHECKS_LABEL="final-commit checks passing"

usage() {
  cat <<'EOF'
Usage:
  pr-evidence.sh --since YYYY-MM-DD --until YYYY-MM-DD
                 (--repo owner/name)... | --org ORG
                 [--author LOGIN|@me] [--confirm-authorised]
                 [--exclude-reviewer LOGIN]... [--redact-titles]
                 [--out DIR] [-h|--help]

Read-only: this script only reads from GitHub via the gh CLI and never writes to it.
Defaults: --author @me; output under $PR_EVIDENCE_DIR if set, else
  $HOME/Documents/pr-evidence-reports/ (or $HOME/pr-evidence-reports/ if there is
  no Documents folder). --out DIR overrides both.
Exit codes: 0 ok, 1 fetch failure, 2 usage or guardrail refusal, 3 missing dependency or auth.
EOF
}

die() { echo "error: $1" >&2; exit "${2:-2}"; }
warn() { echo "warning: $*" >&2; }
lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
need_val() { [[ $# -ge 2 && -n "$2" ]] || die "$1 needs a value"; }

DATE_RE='^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$'
REPO_RE='^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'
LOGIN_RE='^[A-Za-z0-9-]+$'
REVIEWER_RE='^[A-Za-z0-9-]+(\[bot\])?$'

SINCE="" UNTIL="" ORG="" AUTHOR="@me" CONFIRM=false REDACT=false OUT=""
REPOS=()
EXTRA_BOTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since) need_val "$@"; SINCE="$2"; shift 2 ;;
    --until) need_val "$@"; UNTIL="$2"; shift 2 ;;
    --repo) need_val "$@"; REPOS+=("$2"); shift 2 ;;
    --org) need_val "$@"; ORG="$2"; shift 2 ;;
    --author) need_val "$@"; AUTHOR="$2"; shift 2 ;;
    --confirm-authorised) CONFIRM=true; shift ;;
    --exclude-reviewer) need_val "$@"; EXTRA_BOTS+=("$2"); shift 2 ;;
    --redact-titles) REDACT=true; shift ;;
    --out) need_val "$@"; OUT="$2"; shift 2 ;;
    -h | --help) usage; exit 0 ;;
    *) die "unknown argument: $1 (see --help)" ;;
  esac
done

# --- 1. Validate arguments ---------------------------------------------------
[[ -n "$SINCE" && -n "$UNTIL" ]] || die "--since and --until are required"
[[ "$SINCE" =~ $DATE_RE ]] || die "--since must be YYYY-MM-DD"
[[ "$UNTIL" =~ $DATE_RE ]] || die "--until must be YYYY-MM-DD"
[[ ! "$SINCE" > "$UNTIL" ]] || die "--since ($SINCE) is after --until ($UNTIL)"

if [[ ${#REPOS[@]} -gt 0 && -n "$ORG" ]]; then die "use either --repo or --org, not both"; fi
if [[ ${#REPOS[@]} -eq 0 && -z "$ORG" ]]; then die "give at least one --repo owner/name, or --org ORG"; fi
for r in ${REPOS[@]+"${REPOS[@]}"}; do [[ "$r" =~ $REPO_RE ]] || die "invalid --repo: $r (expected owner/name)"; done
[[ -z "$ORG" || "$ORG" =~ $LOGIN_RE ]] || die "invalid --org: $ORG"
[[ "$AUTHOR" == "@me" || "$AUTHOR" =~ $LOGIN_RE ]] || die "invalid --author: $AUTHOR"
for b in ${EXTRA_BOTS[@]+"${EXTRA_BOTS[@]}"}; do [[ "$b" =~ $REVIEWER_RE ]] || die "invalid --exclude-reviewer: $b"; done

# --- 2. Dependencies and auth ------------------------------------------------
for c in gh jq git; do command -v "$c" >/dev/null 2>&1 || die "$c is not installed" 3; done
[[ -f "$METRICS" ]] || die "metrics.jq not found next to this script" 3
gh auth status >/dev/null 2>&1 || die "gh is not authenticated; run: gh auth login" 3
RUN_BY="$(gh api user --jq .login 2>/dev/null)" || die "could not read the signed-in GitHub user (gh api user)" 3

# --- 3. Other-author guardrail (before any PR fetch) -------------------------
if [[ "$AUTHOR" != "@me" && "$(lower "$AUTHOR")" != "$(lower "$RUN_BY")" && "$CONFIRM" != true ]]; then
  cat >&2 <<EOF
refused: --author $AUTHOR is not you ($RUN_BY).
Reporting on another engineer's PRs is an HR and privacy matter. Only do this if you
are authorised (for example as their line manager, with their knowledge), then re-run
with --confirm-authorised. The report will record that you ran it for $AUTHOR.
EOF
  exit 2
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- 4. Repo discovery for --org --------------------------------------------
if [[ -n "$ORG" ]]; then
  gh search prs --owner "$ORG" --author "$AUTHOR" --merged --merged-at "$SINCE..$UNTIL" \
    --limit "$LIMIT" --json repository --jq '.[].repository.nameWithOwner' >"$TMP/discovered.txt" \
    || die "repo discovery failed for org $ORG" 1
  found="$(grep -c . "$TMP/discovered.txt" || true)"
  if [[ "$found" -ge "$LIMIT" ]]; then
    warn "repo discovery hit the $LIMIT-result limit; some repos may be missing — narrow the period or pass --repo explicitly"
  fi
  while IFS= read -r r; do
    [[ -n "$r" ]] && REPOS+=("$r")
  done < <(sort -u "$TMP/discovered.txt")
  [[ ${#REPOS[@]} -gt 0 ]] || warn "no merged PRs found for $AUTHOR in org $ORG for $SINCE..$UNTIL"
fi

# --- 5. Fetch merged PRs per repo -------------------------------------------
i=0
for r in ${REPOS[@]+"${REPOS[@]}"}; do
  i=$((i + 1))
  gh pr list --repo "$r" --state merged --author "$AUTHOR" --search "merged:$SINCE..$UNTIL" \
    --limit "$LIMIT" --json number,title,url,author,createdAt,mergedAt,reviews,statusCheckRollup \
    >"$TMP/raw_$i.json" || die "failed to fetch PRs from $r (check the name and your access)" 1
  jq --arg r "$r" --argjson lim "$LIMIT" \
    '(length >= $lim) as $t | map(. + {repo: $r, repoTruncated: $t})' \
    "$TMP/raw_$i.json" >"$TMP/prs_$i.json"
  n="$(jq length "$TMP/prs_$i.json")"
  echo "fetched $n PRs from $r" >&2
  if [[ "$n" -ge "$LIMIT" ]]; then
    warn "$r hit the $LIMIT-result limit; older PRs may be missing — narrow the period"
  fi
done

if [[ $i -gt 0 ]]; then
  jq -s 'add' "$TMP"/prs_*.json >"$TMP/all.json"
else
  echo '[]' >"$TMP/all.json"
fi

to_json_array() { if [[ $# -eq 0 ]]; then echo '[]'; else printf '%s\n' "$@" | jq -R . | jq -s .; fi; }
BOTS_JSON="$(to_json_array "${DEFAULT_BOTS[@]}" ${EXTRA_BOTS[@]+"${EXTRA_BOTS[@]}"})"
REPOS_JSON="$(to_json_array ${REPOS[@]+"${REPOS[@]}"})"

# --- 6. Output directory -----------------------------------------------------
AUTHOR_SLUG="$AUTHOR"
[[ "$AUTHOR" == "@me" ]] && AUTHOR_SLUG="$RUN_BY"
if [[ -z "$OUT" ]]; then
  # Base dir: $PR_EVIDENCE_DIR, else ~/Documents (macOS, Windows Git Bash), else $HOME (WSL/Linux).
  if [[ -n "${PR_EVIDENCE_DIR:-}" ]]; then
    BASE="$PR_EVIDENCE_DIR"
  elif [[ -d "$HOME/Documents" ]]; then
    BASE="$HOME/Documents/pr-evidence-reports"
  else
    BASE="$HOME/pr-evidence-reports"
  fi
  OUT="$BASE/${AUTHOR_SLUG}_${SINCE}_${UNTIL}_$(date +%Y%m%d%H%M%S)"
fi
mkdir -p "$OUT"
chmod 700 "$OUT"
OUT="$(cd "$OUT" && pwd)"
if git -C "$OUT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  warn "output directory $OUT is inside a git working tree — do not commit these files"
fi

# --- 7. Compute metrics and write files --------------------------------------
META="$(jq -n \
  --arg run_by "$RUN_BY" --arg author "$AUTHOR" --arg author_login "$AUTHOR_SLUG" \
  --arg since "$SINCE" --arg until "$UNTIL" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson repos "$REPOS_JSON" --argjson excluded "$BOTS_JSON" \
  --argjson redacted "$REDACT" --argjson authorised_other "$CONFIRM" \
  --arg label "$LABEL" --arg checks_label "$CHECKS_LABEL" \
  '{run_by: $run_by, author: $author, author_login: $author_login, since: $since, until: $until,
    generated_at: $generated_at, repos: $repos,
    excluded_reviewers: ($excluded + ["any login ending in [bot]"]),
    redacted_titles: $redacted, other_author_confirmed: $authorised_other,
    label: $label, checks_metric_label: $checks_label}')"

jq --argjson bots "$BOTS_JSON" --arg redact "$REDACT" --argjson repos "$REPOS_JSON" --arg mode summary \
  -f "$METRICS" "$TMP/all.json" \
  | jq --argjson meta "$META" '{meta: $meta} + .' >"$OUT/summary.json"

jq -r --argjson bots "$BOTS_JSON" --arg redact "$REDACT" --argjson repos "$REPOS_JSON" --arg mode csv \
  -f "$METRICS" "$TMP/all.json" >"$OUT/pr-evidence.csv"

jq -r '.totals | "merged PRs: \(.merged) | approved by another engineer: \(.approved_pct // "n/a")% | final-commit checks passing: \(.checks_pass_pct // "n/a")%"' \
  "$OUT/summary.json" >&2
echo "OUT_DIR=$OUT"
