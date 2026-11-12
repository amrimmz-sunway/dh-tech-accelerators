# metrics.jq — deterministic metrics for the pr-evidence plugin.
#
# stdin : JSON array of PR objects as returned by
#         gh pr list --json number,title,url,author,createdAt,mergedAt,reviews,statusCheckRollup
#         plus `repo` (owner/name) and `repoTruncated` (bool) added by pr-evidence.sh.
# args  : --argjson bots '[...]'   reviewer logins to exclude (any login ending in [bot] is always excluded)
#         --arg redact true|false  blank PR titles in all output
#         --argjson repos '[...]'  repos queried, so repos with zero PRs still appear
#         --arg mode summary|csv   summary => one JSON object; csv => header + one row per PR (use jq -r)

def round1: (. * 10 | round) / 10;

def pct($n; $d): if $d == 0 then null else ($n / $d * 100 | round1) end;

def is_bot($login): ($login | endswith("[bot]")) or (($bots | index($login)) != null);

# Reviews that count as peer review: not by the PR author, not by a bot.
def countable($pr):
  [ ($pr.reviews // [])[]
    | select(.author.login != null)
    | select(.author.login != $pr.author.login)
    | select(is_bot(.author.login) | not) ];

def item_passes:
  if .__typename == "CheckRun" then ((.conclusion // "") | IN("SUCCESS", "NEUTRAL", "SKIPPED"))
  elif .__typename == "StatusContext" then .state == "SUCCESS"
  else false end;

# "final-commit checks passing": status of the checks on the PR's final head commit.
def checks_state:
  (.statusCheckRollup // []) as $r
  | if ($r | length) == 0 then "none"
    elif all($r[]; item_passes) then "pass"
    else "not_passing" end;

def first_review_hours($pr):
  (countable($pr) | map(.submittedAt | select(. != null) | fromdateiso8601)) as $t
  | if ($t | length) == 0 then null
    else ((($t | min) - ($pr.createdAt | fromdateiso8601)) / 3600 | round1) end;

def median:
  map(select(. != null)) | sort
  | if length == 0 then null
    elif length % 2 == 1 then .[length / 2 | floor]
    else ((.[length / 2 - 1] + .[length / 2]) / 2 | round1) end;

def row:
  . as $pr
  | countable($pr) as $c
  | {
      repo: .repo,
      number: .number,
      title: (if $redact == "true" then "" else ((.title // "") | gsub("[\r\n]+"; " ")) end),
      url: .url,
      created_at: .createdAt,
      merged_at: .mergedAt,
      approved_by_other: ($c | any(.state == "APPROVED")),
      approvers: ($c | map(select(.state == "APPROVED") | .author.login) | unique | join(";")),
      checks: checks_state,
      first_review_hours: first_review_hours($pr)
    };

def stats:
  . as $rows
  | ($rows | length) as $m
  | ($rows | map(select(.approved_by_other)) | length) as $a
  | ($rows | map(select(.checks == "pass")) | length) as $p
  | ($rows | map(select(.checks == "not_passing")) | length) as $np
  | ($rows | map(select(.checks == "none")) | length) as $nn
  | {
      merged: $m,
      approved_by_other: $a,
      approved_pct: pct($a; $m),
      checks_pass: $p,
      checks_not_passing: $np,
      checks_none: $nn,
      checks_pass_pct: pct($p; $p + $np),
      median_first_review_hours: ($rows | map(.first_review_hours) | median)
    };

. as $prs
| ($prs | map(row)) as $rows
| if $mode == "csv" then
    (["repo", "number", "title", "url", "created_at", "merged_at",
      "approved_by_other", "approvers", "checks", "first_review_hours"] | @csv),
    ($rows[]
      | [.repo, .number, .title, .url, .created_at, .merged_at,
         (.approved_by_other | tostring), .approvers, .checks,
         (.first_review_hours // "")]
      | @csv)
  elif $mode == "summary" then
    {
      totals: ($rows | stats),
      repos: [
        (($repos + ($rows | map(.repo))) | unique)[] as $r
        | {repo: $r, truncated: ($prs | any(.repo == $r and .repoTruncated == true))}
          + ($rows | map(select(.repo == $r)) | stats)
      ],
      exceptions: {
        no_approval: [ $rows[] | select(.approved_by_other | not) | {repo, number, url} ],
        checks_not_passing: [ $rows[] | select(.checks == "not_passing") | {repo, number, url} ]
      }
    }
  else error("mode must be summary or csv") end
