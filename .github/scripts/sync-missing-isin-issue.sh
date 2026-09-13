#!/usr/bin/env bash
# Opens/updates/closes a single persistent GitHub issue tracking tickers
# with no ISIN on record — GitHub's own issue-notification emails are the
# "notification/email" GitHub issue #215 asks for, so this deliberately
# does not add any separate email/SMTP integration.
#
# Usage: sync-missing-isin-issue.sh <title> <config-path> <tickers-csv>
#   <title>        Exact, stable issue title used to find the persistent
#                  issue across runs (e.g. "Stock ingestion: tickers
#                  missing ISIN").
#   <config-path>  Repo-relative path to the isin/tax_domicile override
#                  YAML, mentioned in the issue body (e.g.
#                  "packages/stock/config/stocks.prod.yaml").
#   <tickers-csv>  Comma-separated ticker list, or empty when nothing is
#                  missing this run.
#
# Requires GH_TOKEN in the environment (a workflow step should set it from
# secrets.GITHUB_TOKEN) and the job to have `issues: write` permission.
set -euo pipefail

TITLE="$1"
CONFIG_PATH="$2"
TICKERS_CSV="$3"

EXISTING=$(gh issue list --state all --search "\"$TITLE\" in:title" --json number,state,title --limit 20 \
  | jq -c --arg t "$TITLE" '[.[] | select(.title == $t)] | .[0] // empty')
NUMBER=$(jq -r 'if . == null or . == "" then "" else (.number // "") end' <<< "$EXISTING")
STATE=$(jq -r 'if . == null or . == "" then "" else (.state // "") end' <<< "$EXISTING")

if [ -z "$TICKERS_CSV" ]; then
  if [ -n "$NUMBER" ] && [ "$STATE" = "OPEN" ]; then
    gh issue comment "$NUMBER" --body "All tickers now have an ISIN on record as of this run — closing."
    gh issue close "$NUMBER"
    echo "Closed resolved issue #$NUMBER"
  else
    echo "No tickers missing ISIN; nothing to do."
  fi
  exit 0
fi

BODY="The following tickers have no ISIN on record after the latest ingestion run:"$'\n\n'
IFS=',' read -ra TICKERS <<< "$TICKERS_CSV"
for ticker in "${TICKERS[@]}"; do
  BODY+="- \`$ticker\`"$'\n'
done
BODY+=$'\n'"Add an \`isin\`/\`tax_domicile\` override for each in \`$CONFIG_PATH\`, or confirm the ticker itself is correct. This issue is updated automatically by the ingestion workflow and closes itself once every ticker has an ISIN again."

if [ -n "$NUMBER" ]; then
  gh issue edit "$NUMBER" --body "$BODY"
  if [ "$STATE" = "CLOSED" ]; then
    gh issue reopen "$NUMBER"
  fi
  echo "Updated issue #$NUMBER"
else
  gh issue create --title "$TITLE" --body "$BODY"
fi
