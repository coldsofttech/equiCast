# GitHub issue automations

How equicast uses issues in the shared `equicast-support` repo not just to
*track* operational conditions, but as an input channel — a maintainer
replying to an auto-filed issue there can trigger automation back in this
repo (e.g. opening a fix PR). This is the general pattern and how to set up
a new scenario on top of it; **missing ISIN** ([stock-pipeline.md](stock-pipeline.md)/
[etf-pipeline.md](etf-pipeline.md)) is the first scenario built this way, and
more are expected to follow the same shape rather than each inventing its
own trigger/auth mechanism.

## The general pattern

1. **Detect** (`equicast`) — a pipeline job notices a condition worth a
   human's attention and runs a small script to summarize it (e.g.
   `.github/scripts/find_missing_isin.py` reading a freshly-built catalog).
2. **File/track** (`equicast` → `equicast-support`) — a `sync-*-issue.sh`
   script authenticates as `secrets.SUPPORT_ISSUE_TOKEN` and finds-or-creates
   a persistent parent issue plus one native GitHub **sub-issue** per item,
   in `vars.SUPPORT_REPO` (`equicast-support` — the same repo the support
   form's backend files into, see `backend/support/views.py`'s
   `SUPPORT_REPO`). Each sub-issue's body states exactly what a human needs
   to reply with to resolve it. Filed there rather than in `equicast` itself
   so internal engineering tracking stays out of the public-facing repo's
   issue list.
3. **Listen** (`equicast-support`) — an `issue_comment: created` workflow
   watches replies on these auto-filed sub-issues. Gating (all required)
   lives in a script, not inline in the workflow YAML, so untrusted comment
   text is passed in via `env:` rather than interpolated into a shell
   command:
   - commenter's `author_association` is `OWNER` or `MEMBER` — this repo is
     public-facing, so an arbitrary commenter must never be able to trigger
     automation in `equicast`;
   - the issue's parent (via the GraphQL sub-issue API) is one of the
     tracked parent issues for that scenario;
   - the comment body matches the scenario's expected reply format.
4. **Dispatch** (`equicast-support` → `equicast`) — once gated, the script
   fires a `repository_dispatch` against `coldsofttech/equicast`,
   authenticated as `secrets.EQUICAST_DISPATCH_TOKEN` (`GITHUB_TOKEN` can
   only write to the repo a workflow runs in, never across repos — same
   reasoning as `SUPPORT_ISSUE_TOKEN` in the other direction). The
   `client_payload` carries whatever the fix needs, parsed out of the
   triggering issue/comment.
5. **Act** (`equicast`) — a `repository_dispatch`-triggered workflow applies
   the fix deterministically (no LLM/agent involved — see "Why no AI agent
   in the loop" below) and opens a PR whose body starts with GitHub's
   `Closes <owner>/<repo>#<issue-number>` keyword, so the originating
   `equicast-support` issue closes itself the moment the PR merges — this
   relies on the merging account having write access to both repos, which
   is the case here since both are owned by the same account. The checkout
   step pins `ref: main` explicitly rather than trusting anything in the
   payload, and the PR's base is hardcoded to `main` — nothing here can be
   pointed at another branch. On failure, a final step comments back on the
   originating `equicast-support` issue so the maintainer isn't left
   guessing.
6. **Clean up** (`equicast`) — once the fix PR merges, a
   `pull_request: closed` workflow deletes its head branch, scoped by name
   prefix (e.g. `isin/*`) rather than the repo-wide "delete head branches on
   merge" setting, so other branches are never touched regardless of how
   their PR is merged. Each scenario's fix branches should use their own
   short, distinct prefix so this stays easy to scope per scenario.

## Why no AI agent in the loop

The original proposal for missing ISIN (GitHub issue equicast-support#149)
considered having an agent research each ticker's ISIN over the internet.
That was dropped once the design settled on a human supplying the value in
a reply instead (equicast-support#149's discussion): once a human provides
the exact value, applying it is a deterministic find-or-append edit to a
known YAML shape, not something needing judgment — a plain script is
cheaper, has no runaway-cost/turn-limit surface to guard, and its behavior
is fully predictable. Reach for an agent in a future scenario only if the
fix genuinely can't be reduced to a deterministic script (schema drift
across files it must keep in sync, etc.) — and if so, cap it with
`max_turns`, a restricted tool/file allowlist, and a job `timeout-minutes`
before wiring it to fire automatically on every matching reply.

## Secrets and variables inventory

| Name | Set on | Grants | Used by |
| --- | --- | --- | --- |
| `SUPPORT_ISSUE_TOKEN` | `equicast` | `issues:write` on `equicast-support` | every `sync-*-issue.sh` script, and each scenario's fix workflow (failure-comment step) |
| `vars.SUPPORT_REPO` | `equicast` | repo variable, e.g. `coldsofttech/equicast-support` | same scripts, and `backend/support/views.py` |
| `EQUICAST_DISPATCH_TOKEN` | `equicast-support` | write access to `equicast` (fine-grained: Contents: Read and write; or a classic PAT scoped to `public_repo`) | each scenario's `dispatch_*.sh` script |
| `PR_CREATE_TOKEN` | `equicast` | `contents:write` + `pull-requests:write` on `equicast` (fine-grained, single-repo) | each scenario's `repository_dispatch`-triggered fix workflow's PR-creation step — `github.token` can't create PRs unless the repo-wide "Allow GitHub Actions to create and approve pull requests" setting is on, which this project deliberately leaves off (it would grant the capability to every workflow, not just these) |

A new scenario over the same repo pair reuses all three rather than minting
new credentials — only add a new secret if a scenario needs a genuinely
different grant (a different target repo, or narrower access than these
already provide).

## Adding a new scenario

1. **equicast**: detect the condition and write (or extend) a
   `sync-<thing>-issue.sh`-style script that files a persistent parent +
   per-item sub-issue in `equicast-support`, modeled on
   `.github/scripts/sync-missing-isin-issue.sh`. State the exact expected
   reply format in each sub-issue's body.
2. **equicast-support**: add an `issue_comment: created` workflow +
   gating script, modeled on `dispatch-isin-fix.yml` /
   `.github/scripts/dispatch_isin_fix.sh` — recognize the new parent
   issue title(s) and reply format, and fire a new (or reused)
   `repository_dispatch` event type with the payload the fix needs.
3. **equicast**: add a `repository_dispatch`-triggered workflow, modeled on
   `.github/workflows/missing-isin-fix.yml`, pinned to `ref: main`, that
   applies the fix and opens a PR, plus a failure-comment step back to the
   originating issue.
4. Add the new scenario to "Current scenarios" below.
5. Update the secrets/variables table above only if the scenario needs
   something beyond what's already there.

## Current scenarios

### Missing ISIN (stock, ETF)

- **Detect**: `stock-ingestion.yml`/`etf-ingestion.yml`'s `build-catalog`
  job → `find_missing_isin.py` reads the `isin` column of the
  just-uploaded catalog.
- **File**: `sync-missing-isin-issue.sh` → parent issue "Stock ingestion:
  tickers missing ISIN" / "ETF ingestion: tickers missing ISIN", with one
  sub-issue per ticker (e.g. "AAPL: missing ISIN") pointing at
  `packages/stock/config/stocks.prod.yaml` or
  `packages/etf/config/etfs.prod.yaml`.
- **Listen/Dispatch**: `equicast-support`'s `dispatch-isin-fix.yml` +
  `dispatch_isin_fix.sh` — gated on author association, the tracked parent,
  and a reply matching `ISIN: <code>` (optional `TAX_DOMICILE: <code>`) —
  fires the `missing-isin-provided` event.
- **Act**: `.github/workflows/missing-isin-fix.yml` +
  `.github/scripts/apply_isin_override.py` — cross-checks the ticker
  against every known `*.prod.yaml` (erroring loudly on a mismatch or
  ambiguity instead of guessing), edits only that entry's lines, re-parses
  to validate before writing, and opens a PR from an `isin/<TICKER>` branch
  whose body opens with `Closes <owner>/<repo>#<issue-number>` — GitHub's
  cross-repo closing keyword, which closes the originating sub-issue the
  moment the PR merges (works here because the account merging owns both
  repos). Otherwise the sub-issue would sit open until the next scheduled
  ingestion run confirms the ticker has an ISIN again.
- **Clean up**: `cleanup-merged-isin-branches.yml` deletes the
  `isin/<TICKER>` branch once its PR merges.
- Design history: GitHub issues equicast-support#149,
  equicast-support#197, equicast-support#198, equicast#289.

## Setting up a new environment/fork

- Create `SUPPORT_ISSUE_TOKEN` on `equicast` (a token with `issues:write`
  on wherever the support repo will be) and set `vars.SUPPORT_REPO` to that
  repo's `owner/name`.
- Create `EQUICAST_DISPATCH_TOKEN` on the support repo, scoped to write
  access on `equicast` only.
- Create `PR_CREATE_TOKEN` on `equicast` itself, scoped to `contents:write`
  + `pull-requests:write` on `equicast` only.
- None of these tokens needs any permission beyond what's in the inventory
  table above — resist widening scope "just in case."

## Troubleshooting

**A reply on a sub-issue never triggers anything** — check, in order: the
commenter's association is `OWNER`/`MEMBER`; the comment matches the
scenario's exact expected format; `EQUICAST_DISPATCH_TOKEN` exists and
hasn't expired on `equicast-support`; the sub-issue's parent is one of the
titles the listening script checks for.

**Dispatch fires (visible under `equicast-support`'s workflow run) but no
PR appears in `equicast`** — check the corresponding
`repository_dispatch`-triggered workflow's run under `equicast`'s Actions
tab. For missing ISIN, the most likely cause is
`apply_isin_override.py` refusing to write because the ticker wasn't found
in the config path the issue named, or was found in more than one — by
design, not a bug to silently work around.

**A PAT stops working with no code change** — check its expiration first;
none of these tokens is set to never expire.

**The fix PR merges but the originating sub-issue stays open** — check the
PR body actually starts with `Closes <owner>/<repo>#<issue-number>`
(GitHub only honors the keyword, not a plain link) and that the account
merging the PR has write access to `equicast-support`. Failing that, it
still self-heals: the next scheduled ingestion run's
`sync-missing-isin-issue.sh` closes any sub-issue whose ticker now has an
ISIN on record, just not immediately.

**The fix branch/commit exist but the run fails on `gh pr create` with
`GitHub Actions is not permitted to create or approve pull requests`** —
`PR_CREATE_TOKEN` is missing/expired on `equicast`, or the workflow's PR
step is still using `github.token`. This is expected behavior, not a
transient failure: GitHub blocks the default token from creating PRs
unless the repo-wide setting is explicitly turned on, which this project
deliberately leaves off (see the inventory table above).

## Security notes

- Every reply-triggered dispatch is gated on `author_association` — comment
  text on a public repo is otherwise attacker-controlled input.
- Cross-repo PATs are scoped to the single target repo and the minimum
  permission that repo's API calls need, not the whole `repo` scope
  org-wide.
- `repository_dispatch`-triggered workflows in `equicast` never trust a
  branch/ref carried in the payload — checkout is always pinned to
  `ref: main`, and the resulting PR's base is always `main`.
