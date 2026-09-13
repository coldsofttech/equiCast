#!/usr/bin/env bash
# Opens/updates a persistent parent GitHub issue per pipeline ("Stock
# ingestion: tickers missing ISIN" / "ETF ingestion: tickers missing
# ISIN") and, under it, one native GitHub sub-issue per ticker currently
# missing an ISIN — GitHub's own sub-issues feature (a real parent/child
# link, not just a checklist in one issue body). Each ticker can then be
# worked and closed independently, e.g. a fix PR can `Closes #<sub-issue>`.
# GitHub's own issue-notification emails are the "notification/email"
# GitHub issue #215 asks for, so this deliberately adds no separate
# email/SMTP integration.
#
# Usage: sync-missing-isin-issue.sh <parent-title> <pipeline-label> <config-path> <tickers-csv>
#   <parent-title>   Exact, stable parent issue title used to find it
#                     across runs (e.g. "Stock ingestion: tickers missing
#                     ISIN").
#   <pipeline-label> Short label for the parent issue's body (e.g.
#                     "stock" or "ETF").
#   <config-path>    Repo-relative path to the isin/tax_domicile override
#                     YAML, mentioned in each sub-issue body (e.g.
#                     "packages/stock/config/stocks.prod.yaml").
#   <tickers-csv>     Comma-separated ticker list currently missing an
#                     ISIN, or empty when nothing is missing this run.
#
# Requires GH_TOKEN in the environment (a workflow step should set it from
# secrets.GITHUB_TOKEN) and the job to have `issues: write` permission.
# The parent issue's own open/closed state is never touched here (only
# its sub-issues are auto-managed) — it's a long-lived tracker, not a
# per-run alert.
set -euo pipefail

PARENT_TITLE="$1"
PIPELINE_LABEL="$2"
CONFIG_PATH="$3"
TICKERS_CSV="$4"

REPO_NWO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
OWNER="${REPO_NWO%/*}"
NAME="${REPO_NWO#*/}"

# Find (any state) or create the persistent parent issue.
PARENT_NUMBER=$(gh issue list --state all \
  --search "\"$PARENT_TITLE\" in:title" --json number,title --limit 20 \
  | jq -r --arg t "$PARENT_TITLE" '[.[] | select(.title == $t)] | .[0].number // empty')

PARENT_BODY="Tracks tickers with no ISIN on record after $PIPELINE_LABEL ingestion runs. Each missing ticker gets its own sub-issue below, opened/closed automatically as it appears/resolves. See \`$CONFIG_PATH\` to add an \`isin\`/\`tax_domicile\` override."

if [ -z "$PARENT_NUMBER" ]; then
  PARENT_URL=$(gh issue create --title "$PARENT_TITLE" --body "$PARENT_BODY")
  PARENT_NUMBER="${PARENT_URL##*/}"
  echo "Created parent issue #$PARENT_NUMBER"
else
  # Keeps an already-existing parent's body in sync with this format —
  # e.g. one created by an earlier, checklist-body version of this script.
  gh issue edit "$PARENT_NUMBER" --body "$PARENT_BODY"
fi

# Existing sub-issues of the parent (number/title/state) via GraphQL --
# `gh issue view --json subIssues` doesn't document its per-node field
# set, so this asks for exactly what's needed instead of relying on it.
EXISTING=$(gh api graphql -f query='
  query($owner:String!, $repo:String!, $number:Int!) {
    repository(owner:$owner, name:$repo) {
      issue(number:$number) {
        subIssues(first: 100) {
          nodes { number title state }
        }
      }
    }
  }' -F owner="$OWNER" -F repo="$NAME" -F number="$PARENT_NUMBER" \
  | jq -c '.data.repository.issue.subIssues.nodes')

IFS=',' read -ra MISSING <<< "$TICKERS_CSV"

# Open a sub-issue for each newly-missing ticker, or reopen one that was
# previously resolved and has since gone missing again.
for ticker in "${MISSING[@]:-}"; do
  [ -z "$ticker" ] && continue
  SUB_TITLE="$ticker: missing ISIN"
  MATCH=$(jq -c --arg t "$SUB_TITLE" '[.[] | select(.title == $t)] | .[0] // empty' <<< "$EXISTING")
  SUB_NUMBER=$(jq -r 'if . == null or . == "" then "" else (.number // "") end' <<< "$MATCH")
  SUB_STATE=$(jq -r 'if . == null or . == "" then "" else (.state // "") end' <<< "$MATCH")

  if [ -z "$SUB_NUMBER" ]; then
    SUB_BODY="\`$ticker\` has no ISIN on record as of the latest ingestion run. Add an \`isin\`/\`tax_domicile\` override for it in \`$CONFIG_PATH\`, or confirm the ticker itself is correct. This sub-issue closes automatically once \`$ticker\` has an ISIN again."
    gh issue create --title "$SUB_TITLE" --body "$SUB_BODY" --parent "$PARENT_NUMBER" >/dev/null
    echo "Opened sub-issue for $ticker"
  elif [ "$SUB_STATE" = "CLOSED" ]; then
    gh issue reopen "$SUB_NUMBER"
    gh issue comment "$SUB_NUMBER" --body "Missing an ISIN again as of the latest ingestion run."
    echo "Reopened sub-issue #$SUB_NUMBER for $ticker"
  fi
  # else: already open and tracked, nothing to do.
done

# Close any open sub-issue for a ticker that's no longer missing.
while IFS= read -r row; do
  [ -z "$row" ] && continue
  NUMBER=$(jq -r '.number' <<< "$row")
  TITLE=$(jq -r '.title' <<< "$row")
  STATE=$(jq -r '.state' <<< "$row")
  [ "$STATE" = "OPEN" ] || continue
  TICKER="${TITLE%: missing ISIN}"
  STILL_MISSING=false
  for ticker in "${MISSING[@]:-}"; do
    if [ "$ticker" = "$TICKER" ]; then
      STILL_MISSING=true
      break
    fi
  done
  if [ "$STILL_MISSING" = false ]; then
    gh issue comment "$NUMBER" --body "\`$TICKER\` now has an ISIN on record — closing."
    gh issue close "$NUMBER"
    echo "Closed resolved sub-issue #$NUMBER for $TICKER"
  fi
done < <(jq -c '.[]' <<< "$EXISTING")
