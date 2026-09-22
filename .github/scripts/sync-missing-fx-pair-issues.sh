#!/usr/bin/env bash
# Opens one GitHub issue per FX pair a stock/ETF holding currency needs but
# packages/fx/config/fx_pairs.<env>.yaml doesn't configure
# (equicast-support#164) - e.g. "Missing FX pair: USD:INR" - as reported by
# equicast-fx-find-missing-pairs (see equicast_fx.missing_pairs for exactly
# which pairs count as needed).
#
# One issue per directed pair, not per pipeline: stock and ETF runs both
# feed this, and whichever reports a pair first opens its issue - the other
# just finds it already open. For the same reason, an issue is only ever
# closed here once its pair is actually configured, never merely because
# this run's catalog no longer needs it (the other pipeline's might).
#
# Each issue is shaped for equicast-support's config-change scenario
# (.github/scripts/scenarios/config-change.sh there): the "ticker-request"
# label plus an environment label, and a "**Ticker:** FROM:TO" body line it
# falls back to for KEY - so a maintainer replying `ASSET_CLASS: fx` opens
# the fx_pairs PR via manage_config_entry.py, and that PR closes the issue
# once merged. Filed in equicast-support (not this repo), same reasoning as
# sync-missing-isin-issue.sh.
#
# Usage: sync-missing-fx-pair-issues.sh <target-repo> <env-label> <pipeline-label> <config-path> <result-json>
#   <target-repo>    owner/repo to file issues in - pass `${{ vars.SUPPORT_REPO }}`.
#   <env-label>      "production" or "development" - must match the FX
#                     config checked, since config-change.sh picks the
#                     config file to edit from this label.
#   <pipeline-label> Short label for the issue body (e.g. "stock" or "ETF").
#   <config-path>    Repo-relative path of the FX config checked (e.g.
#                     "packages/fx/config/fx_pairs.prod.yaml").
#   <result-json>    Path to equicast-fx-find-missing-pairs' JSON output.
#
# Requires GH_TOKEN with issues:write on <target-repo> - set from
# `${{ secrets.SUPPORT_ISSUE_TOKEN }}`, same as sync-missing-isin-issue.sh.
set -euo pipefail

TARGET_REPO="$1"
ENV_LABEL="$2"
PIPELINE_LABEL="$3"
CONFIG_PATH="$4"
RESULT_JSON="$5"

TITLE_PREFIX="Missing FX pair: "

# Every issue this script has ever filed for <env-label> (any state),
# matched on exact title prefix since GitHub's search is fuzzy - scoped to
# the label so a run checking one environment's config never reopens or
# closes another environment's issue for the same pair.
EXISTING=$(gh issue list --repo "$TARGET_REPO" --state all --label "$ENV_LABEL" \
  --search "\"$TITLE_PREFIX\" in:title" --json number,title,state,stateReason --limit 1000 \
  | jq -c --arg p "$TITLE_PREFIX" '[.[] | select(.title | startswith($p))]')

# Open an issue per newly-missing pair, or reopen one that was resolved
# (closed as completed) and has since gone missing again. One closed as
# "not planned" is left closed - a maintainer's decision not to track that
# pair shouldn't be undone by every nightly run.
while IFS= read -r row; do
  [ -z "$row" ] && continue
  FROM=$(jq -r '.from' <<< "$row")
  TO=$(jq -r '.to' <<< "$row")
  TICKERS=$(jq -r '.tickers | join(", ")' <<< "$row")
  KEY="$FROM:$TO"
  TITLE="$TITLE_PREFIX$KEY"

  MATCH=$(jq -c --arg t "$TITLE" '[.[] | select(.title == $t)] | .[0] // empty' <<< "$EXISTING")
  if [ -z "$MATCH" ]; then
    BODY=$(cat <<EOF
The $PIPELINE_LABEL ingestion pipeline found holdings priced in a currency that can't be converted into one of the UI's currencies (\`frontend/src/config/currencies.json\`): the \`$FROM\` → \`$TO\` pair isn't configured in \`$CONFIG_PATH\`.

**Ticker:** $KEY

Holdings needing it: $TICKERS

Reply \`ASSET_CLASS: fx\` to open a PR adding \`$KEY\` to \`$CONFIG_PATH\`. This issue also closes automatically once the pair is configured.
EOF
)
    gh issue create --repo "$TARGET_REPO" --title "$TITLE" --body "$BODY" \
      --label "ticker-request" --label "$ENV_LABEL" >/dev/null
    echo "Opened issue for $KEY"
    continue
  fi

  NUMBER=$(jq -r '.number' <<< "$MATCH")
  STATE=$(jq -r '.state' <<< "$MATCH")
  REASON=$(jq -r '.stateReason // ""' <<< "$MATCH")
  if [ "$STATE" = "CLOSED" ] && [ "$REASON" != "NOT_PLANNED" ]; then
    gh issue reopen "$NUMBER" --repo "$TARGET_REPO"
    gh issue comment "$NUMBER" --repo "$TARGET_REPO" \
      --body "\`$KEY\` is missing from \`$CONFIG_PATH\` again as of the latest $PIPELINE_LABEL ingestion run. Holdings needing it: $TICKERS"
    echo "Reopened issue #$NUMBER for $KEY"
  fi
  # else: already open, or deliberately closed as not planned.
done < <(jq -c '.missing[]' "$RESULT_JSON")

# Close any open issue whose pair is now configured.
while IFS= read -r row; do
  [ -z "$row" ] && continue
  NUMBER=$(jq -r '.number' <<< "$row")
  KEY=$(jq -r --arg p "$TITLE_PREFIX" '.title | ltrimstr($p)' <<< "$row")
  if jq -e --arg k "$KEY" 'any(.configured[]; . == $k)' "$RESULT_JSON" >/dev/null; then
    gh issue close "$NUMBER" --repo "$TARGET_REPO" --reason completed \
      --comment "\`$KEY\` is now configured in \`$CONFIG_PATH\` - closing."
    echo "Closed resolved issue #$NUMBER for $KEY"
  fi
done < <(jq -c '.[] | select(.state == "OPEN")' <<< "$EXISTING")
