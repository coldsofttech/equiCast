#!/usr/bin/env bash
# GitHub issue equicast-support#145: a failed ingestion run was previously
# only visible via the red X on the Actions tab. Opens/updates a persistent
# parent GitHub issue per pipeline ("Stock ingestion: pipeline failures")
# reporting overall job/infra health - reused as the parent for
# equicast-support#145's per-ticker sub-issues too (see
# sync-pipeline-failure-subissues.sh, called separately). A failed run
# reopens the parent (if closed) and adds a comment; the next successful run
# adds a comment and closes it again.
#
# Unlike sync-missing-isin-issue.sh's parent (whose own open/closed state is
# never touched - only its sub-issues are auto-managed), THIS issue's own
# state IS the "is the pipeline currently healthy" signal: it only ever
# tracks one pipeline at a time, unlike missing-ISIN's many-tickers-at-once
# case, so there's no need for a sub-issue per failed run the way missing-
# ISIN needs one sub-issue per ticker.
#
# Usage: sync-pipeline-failure-issue.sh <target-repo> <parent-title> <status> <run-url> <failed-jobs-csv>
#   <target-repo>      owner/repo to file the parent issue in (pass
#                       `${{ vars.SUPPORT_REPO }}`, same as
#                       sync-missing-isin-issue.sh).
#   <parent-title>      Exact, stable issue title used to find it across
#                       runs (e.g. "Stock ingestion: pipeline failures").
#   <status>            "failure" or "success" - this run's overall
#                       job/infra outcome (see the calling workflow's
#                       "Determine pipeline status" step).
#   <run-url>            This workflow run's URL, included in the comment.
#   <failed-jobs-csv>    Comma-separated failed job names for this run, or
#                       empty. Ignored when <status> is "success".
#
# Requires GH_TOKEN in the environment (issues:write on <target-repo>) - see
# sync-missing-isin-issue.sh's header for the full rationale (same
# SUPPORT_ISSUE_TOKEN secret, since the default GITHUB_TOKEN has no access
# to <target-repo>).
#
# Prints the parent issue's number as the only line on stdout - all logging
# goes to stderr - so a caller can capture it for
# sync-pipeline-failure-subissues.sh. The parent is found-or-created
# regardless of <status>, since sub-issues may need to attach to it even on
# a run whose overall status is "success".
set -euo pipefail

TARGET_REPO="$1"
PARENT_TITLE="$2"
STATUS="$3"
RUN_URL="$4"
FAILED_JOBS="$5"

MATCH=$(gh issue list --repo "$TARGET_REPO" --state all \
  --search "\"$PARENT_TITLE\" in:title" --json number,title,state --limit 20 \
  | jq -c --arg t "$PARENT_TITLE" '[.[] | select(.title == $t)] | .[0] // empty')
PARENT_NUMBER=$(jq -r 'if . == null or . == "" then "" else (.number // "") end' <<< "$MATCH")
PARENT_STATE=$(jq -r 'if . == null or . == "" then "" else (.state // "") end' <<< "$MATCH")

if [ -z "$PARENT_NUMBER" ]; then
  PARENT_BODY="Tracks job/infra health for this pipeline's ingestion workflow. Opened automatically on the first failure, closed automatically once a subsequent run succeeds. See this issue's sub-issues for any ticker/pair/benchmark whose own data extraction is currently failing, independent of this issue's own open/closed state."
  PARENT_URL=$(gh issue create --repo "$TARGET_REPO" --title "$PARENT_TITLE" --body "$PARENT_BODY")
  PARENT_NUMBER="${PARENT_URL##*/}"
  echo "Created parent issue #$PARENT_NUMBER" >&2
fi

# >/dev/null on every gh issue mutation below: `gh issue comment`/`reopen`/
# `close` print their own result (e.g. the new comment's URL) to stdout,
# which would otherwise leak into the caller's `PARENT_NUMBER=$(bash
# sync-pipeline-failure-issue.sh ...)` capture ahead of this script's own
# trailing `echo "$PARENT_NUMBER"` - corrupting the single-line stdout
# contract documented above and breaking the caller's GITHUB_OUTPUT write.
if [ "$STATUS" = "failure" ]; then
  JOBS="${FAILED_JOBS:-(unspecified job)}"
  if [ "$PARENT_STATE" = "CLOSED" ]; then
    gh issue reopen "$PARENT_NUMBER" --repo "$TARGET_REPO" >/dev/null
  fi
  gh issue comment "$PARENT_NUMBER" --repo "$TARGET_REPO" \
    --body "Run failed: $RUN_URL — failed job(s): $JOBS." >/dev/null
  echo "Reported failure on parent issue #$PARENT_NUMBER" >&2
elif [ "$PARENT_STATE" = "OPEN" ]; then
  gh issue comment "$PARENT_NUMBER" --repo "$TARGET_REPO" \
    --body "Resolved by a successful run: $RUN_URL" >/dev/null
  gh issue close "$PARENT_NUMBER" --repo "$TARGET_REPO" >/dev/null
  echo "Closed resolved parent issue #$PARENT_NUMBER" >&2
fi

echo "$PARENT_NUMBER"
