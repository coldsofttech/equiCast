#!/usr/bin/env bash
# GitHub issue equicast-support#145: within an otherwise-healthy ingestion
# run, one ticker's/pair's/benchmark's data extraction can still fail on its
# own (equicast-stock/etf/fx/benchmark's cli.run() no longer aborts the
# whole chunk on a single failed task - see each package's writer.py
# write_failures_manifest and cli.py run() for where failures.json comes
# from). Attaches one native GitHub sub-issue per currently-failing item to
# the parent pipeline-failure issue sync-pipeline-failure-issue.sh manages -
# same parent/sub-issue GraphQL machinery as sync-missing-isin-issue.sh, see
# that script's header for the general approach.
#
# Usage: sync-pipeline-failure-subissues.sh <target-repo> <parent-number> <pipeline-label> <run-url> <failures-json-path>
#   <target-repo>        owner/repo the parent issue lives in.
#   <parent-number>      The parent issue's number, from
#                       sync-pipeline-failure-issue.sh's stdout.
#   <pipeline-label>      Short label for sub-issue bodies (e.g. "stock").
#   <run-url>            This workflow run's URL, included in each comment.
#   <failures-json-path>  Path to a local JSON file: a flat array of
#                       {"ticker", "task", "error"} objects (one per
#                       item/task that failed this run - see
#                       merge_failures.py, which merges every chunk's
#                       failures-*.json into this one file first).
#
# IMPORTANT: only call this for a full, untargeted run where ingest actually
# executed (i.e. plan.outputs.targeted != 'true' and, where the pipeline
# has one, run_ingest == 'true') and ingest's result is 'success' or
# 'failure' (not 'skipped'/'cancelled'). The "close" pass below infers
# "<ticker> is resolved" from "<ticker> isn't in this run's failures", which
# only holds when every configured item was actually attempted this run - a
# targeted run (the "tickers" workflow_dispatch input) or a run whose legs
# were cancelled mid-flight would otherwise falsely "resolve" every item it
# simply didn't attempt.
#
# Requires GH_TOKEN in the environment (issues:write on <target-repo>) -
# same as sync-pipeline-failure-issue.sh/sync-missing-isin-issue.sh.
set -euo pipefail

TARGET_REPO="$1"
PARENT_NUMBER="$2"
PIPELINE_LABEL="$3"
RUN_URL="$4"
FAILURES_JSON_PATH="$5"

OWNER="${TARGET_REPO%/*}"
NAME="${TARGET_REPO#*/}"

FAILURES=$(cat "$FAILURES_JSON_PATH")

# One group per currently-failing ticker/pair/benchmark, each carrying every
# task that failed for it this run (e.g. both "prices" and "events" can fail
# independently for the same ticker).
GROUPED=$(jq -c 'group_by(.ticker) | map({ticker: .[0].ticker, items: map({task, error})})' <<< "$FAILURES")

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

# Open a sub-issue for each newly-failing item, or reopen/comment on one
# that's failing again after a previous run resolved it.
while IFS= read -r group; do
  [ -z "$group" ] && continue
  TICKER=$(jq -r '.ticker' <<< "$group")
  SUB_TITLE="$TICKER: data extraction failed"
  DETAIL=$(jq -r '.items | map("- \(.task): \(.error)") | join("\n")' <<< "$group")
  MATCH=$(jq -c --arg t "$SUB_TITLE" '[.[] | select(.title == $t)] | .[0] // empty' <<< "$EXISTING")
  SUB_NUMBER=$(jq -r 'if . == null or . == "" then "" else (.number // "") end' <<< "$MATCH")
  SUB_STATE=$(jq -r 'if . == null or . == "" then "" else (.state // "") end' <<< "$MATCH")

  if [ -z "$SUB_NUMBER" ]; then
    SUB_BODY="\`$TICKER\` failed to fetch during the latest $PIPELINE_LABEL ingestion run ($RUN_URL):

$DETAIL

This sub-issue closes automatically once \`$TICKER\` fetches successfully again."
    gh issue create --repo "$TARGET_REPO" --title "$SUB_TITLE" --body "$SUB_BODY" --parent "$PARENT_NUMBER" >/dev/null
    echo "Opened sub-issue for $TICKER"
  else
    if [ "$SUB_STATE" = "CLOSED" ]; then
      gh issue reopen "$SUB_NUMBER" --repo "$TARGET_REPO"
    fi
    gh issue comment "$SUB_NUMBER" --repo "$TARGET_REPO" --body "Failed again during the latest run ($RUN_URL):

$DETAIL"
    echo "Reopened/updated sub-issue #$SUB_NUMBER for $TICKER"
  fi
  # else: already open and tracked, nothing further to do beyond the
  # comment above.
done < <(jq -c '.[]' <<< "$GROUPED")

# Close any open sub-issue for an item that's no longer failing (see this
# script's header for why it's only safe to reach this point on a full,
# untargeted, actually-attempted run).
FAILING_TICKERS=$(jq -r '.[].ticker' <<< "$GROUPED")
while IFS= read -r row; do
  [ -z "$row" ] && continue
  NUMBER=$(jq -r '.number' <<< "$row")
  TITLE=$(jq -r '.title' <<< "$row")
  STATE=$(jq -r '.state' <<< "$row")
  [ "$STATE" = "OPEN" ] || continue
  TICKER="${TITLE%: data extraction failed}"

  STILL_FAILING=false
  while IFS= read -r failing_ticker; do
    if [ "$failing_ticker" = "$TICKER" ]; then
      STILL_FAILING=true
      break
    fi
  done <<< "$FAILING_TICKERS"

  if [ "$STILL_FAILING" = false ]; then
    gh issue comment "$NUMBER" --repo "$TARGET_REPO" --body "\`$TICKER\` fetched successfully again — closing."
    gh issue close "$NUMBER" --repo "$TARGET_REPO"
    echo "Closed resolved sub-issue #$NUMBER for $TICKER"
  fi
done < <(jq -c '.[]' <<< "$EXISTING")
