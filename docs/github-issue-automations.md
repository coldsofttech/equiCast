# GitHub issue automations

How equicast uses issues in the shared `equicast-support` repo not just to
*track* operational conditions, but as an input channel — a maintainer
replying to an auto-filed issue there can trigger automation back in this
repo (e.g. opening a fix PR). This is the general pattern and how to set up
a new scenario on top of it; **missing ISIN** ([stock-pipeline.md](stock-pipeline.md)/
[etf-pipeline.md](etf-pipeline.md)) was the first scenario built this way,
**config change** followed once it became clear the shape generalized, and
more are expected to follow the same shape rather than each inventing its
own trigger/auth mechanism.

Every scenario shares one workflow pair rather than getting its own: one
`issue_comment` listener in `equicast-support`, one `repository_dispatch`
receiver in `equicast`, one branch-cleanup workflow in `equicast`. A
scenario is a small, self-contained plugin dropped into each side — see
"Adding a new scenario" below.

## The general pattern

1. **Detect** (`equicast`) — a pipeline job notices a condition worth a
   human's attention and runs a small script to summarize it (e.g.
   `.github/scripts/find_missing_isin.py` reading a freshly-built catalog).
   Not every scenario has this step — **config change**'s input is already
   a GitHub issue, filed directly by the support form (see "Current
   scenarios" below).
2. **File/track** (`equicast` → `equicast-support`) — a `sync-*-issue.sh`
   script authenticates as `secrets.SUPPORT_ISSUE_TOKEN` and finds-or-creates
   a persistent parent issue plus one native GitHub **sub-issue** per item,
   in `vars.SUPPORT_REPO` (`equicast-support` — the same repo the support
   form's backend files into, see `backend/support/views.py`'s
   `SUPPORT_REPO`). Each sub-issue's body states exactly what a human needs
   to reply with to resolve it. Filed there rather than in `equicast` itself
   so internal engineering tracking stays out of the public-facing repo's
   issue list.
3. **Listen** (`equicast-support`) — the single `dispatch-issue-automation.yml`
   workflow (`issue_comment: created`) hands every comment to
   `.github/scripts/dispatch_issue_automation.sh`, which gates the one
   thing every scenario needs — commenter's `author_association` is `OWNER`
   or `MEMBER`, since this repo is public-facing and an arbitrary commenter
   must never be able to trigger automation in `equicast` — then tries each
   file in `.github/scripts/scenarios/*.sh` in turn. A scenario file owns
   everything specific to it: its own identity check (e.g. "is this a
   sub-issue of one of my tracked parents", "does this issue carry my
   label"), its own reply-format parsing, and building its own
   `client_payload`. Untrusted comment/issue text is passed in via `env:`,
   never interpolated into a shell command.
4. **Dispatch** (`equicast-support` → `equicast`) — once a scenario
   confirms the issue is its own and the reply parses, it calls the shared
   `dispatch_event` helper, which fires a `repository_dispatch` against
   `coldsofttech/equicast`, authenticated as `secrets.EQUICAST_DISPATCH_TOKEN`
   (`GITHUB_TOKEN` can only write to the repo a workflow runs in, never
   across repos — same reasoning as `SUPPORT_ISSUE_TOKEN` in the other
   direction). Each scenario keeps its own `event_type` name (e.g.
   `missing-isin-provided`) — GitHub echoes it back as `github.event.action`
   on the receiving end, which is how step 5 routes without a redundant
   field in the payload.
5. **Act** (`equicast`) — the single `issue-automation-fix.yml` workflow
   (`repository_dispatch`, listening for every scenario's `event_type`)
   routes on `github.event.action` to that scenario's own apply logic
   (a case arm calling that scenario's existing script, e.g.
   `apply_isin_override.py`), then shares the same
   branch/commit/push/PR-create/auto-merge mechanics for every scenario.
   The fix is applied deterministically — no LLM/agent involved, see "Why
   no AI agent in the loop" below — and the PR body starts with GitHub's
   `Closes <owner>/<repo>#<issue-number>` keyword, so the originating
   `equicast-support` issue closes itself the moment the PR merges (this
   relies on the merging account having write access to both repos, true
   here since both are owned by the same account). The checkout step pins
   `ref: main` explicitly rather than trusting anything in the payload, and
   the PR's base is hardcoded to `main` — nothing here can be pointed at
   another branch. On failure, a final step comments back on the
   originating `equicast-support` issue so the maintainer isn't left
   guessing.
6. **Clean up** (`equicast`) — once a fix PR merges, the single
   `cleanup-merged-automation-branches.yml` workflow (`pull_request: closed`)
   deletes its head branch, via one step per scenario each gated on its
   own prefix (`isin/`, `config/`, …) rather than the repo-wide "delete
   head branches on merge" setting, so other branches are never touched
   regardless of how their PR is merged. Each scenario should pick its own
   short, distinct prefix and add its own step, so a future scenario whose
   cleanup needs more than "delete the branch" has somewhere to put that
   without touching the others.

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
| `SUPPORT_ISSUE_TOKEN` | `equicast` | `issues:write` on `equicast-support` | every `sync-*-issue.sh` script, and `issue-automation-fix.yml`'s failure-comment step |
| `vars.SUPPORT_REPO` | `equicast` | repo variable, e.g. `coldsofttech/equicast-support` | same scripts, and `backend/support/views.py` |
| `EQUICAST_DISPATCH_TOKEN` | `equicast-support` | write access to `equicast` (fine-grained: Contents: Read and write; or a classic PAT scoped to `public_repo`) | `dispatch_issue_automation.sh`'s shared `dispatch_event` helper |
| `PR_CREATE_TOKEN` | `equicast` | `contents:write` + `pull-requests:write` on `equicast` (fine-grained, single-repo) | `issue-automation-fix.yml`'s PR-creation step — `github.token` can't create PRs unless the repo-wide "Allow GitHub Actions to create and approve pull requests" setting is on, which this project deliberately leaves off (it would grant the capability to every workflow, not just this one) |

A new scenario over the same repo pair reuses all three rather than minting
new credentials — only add a new secret if a scenario needs a genuinely
different grant (a different target repo, or narrower access than these
already provide).

## Adding a new scenario

1. **equicast** (only if the condition needs detecting, rather than already
   arriving as an issue): write a `sync-<thing>-issue.sh`-style script that
   files a persistent parent + per-item sub-issue in `equicast-support`,
   modeled on `.github/scripts/sync-missing-isin-issue.sh`. State the exact
   expected reply format in each sub-issue's body.
2. **equicast-support**: add `.github/scripts/scenarios/<thing>.sh` defining
   a `scenario_run` function (see `dispatch_issue_automation.sh`'s header
   for the exact contract — return `100` the moment the issue/comment is
   confirmed not yours, `0` once you've either dispatched or logged a
   reason to ignore). Use the shared `has_label`, `dispatch_event`,
   `OWNER`/`NAME`/`TARGET_REPO` the driver already provides. No workflow
   YAML or new dispatch script needed — `dispatch-issue-automation.yml`
   picks up every file in that directory automatically.
3. **equicast**: add a case arm to `issue-automation-fix.yml`'s "Apply the
   fix" step, keyed on the new `event_type` (`github.event.action`) —
   run your scenario's own apply script (or write a new one, modeled on
   `apply_isin_override.py`/`manage_config_entry.py`) and set that step's
   `branch`/`git_add`/`commit_message`/`subject` outputs; add a matching
   case arm to the "Open PR" step for the body text. Everything else
   (checkout pinned to `ref: main`, branch/commit/push, PR creation,
   auto-merge, failure-comment) is already shared.
4. **equicast**: add a step to `cleanup-merged-automation-branches.yml`,
   gated on `startsWith(github.event.pull_request.head.ref, '<your-prefix>/')`,
   that deletes the merged branch — or does whatever else your scenario's
   cleanup needs.
5. Add the new scenario to "Current scenarios" below.
6. Update the secrets/variables table above only if the scenario needs
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
- **Listen/Dispatch**: `.github/scripts/scenarios/missing-isin.sh` (on
  `equicast-support`) — identity is "issue is a sub-issue of one of the
  two tracked parents" (via the GraphQL sub-issue API), reply must match
  `ISIN: <code>` (optional `TAX_DOMICILE: <code>`) — fires the
  `missing-isin-provided` event.
- **Act**: `issue-automation-fix.yml`'s `missing-isin-provided` case arm +
  `.github/scripts/apply_isin_override.py` — cross-checks the ticker
  against every known `*.prod.yaml` (erroring loudly on a mismatch or
  ambiguity instead of guessing), edits only that entry's lines, re-parses
  to validate before writing, and opens a PR from an `isin/<TICKER>` branch.
  Otherwise the sub-issue would sit open until the next scheduled
  ingestion run confirms the ticker has an ISIN again.
- **Clean up**: `cleanup-merged-automation-branches.yml`'s `isin/` prefix.
- Design history: GitHub issues equicast-support#149,
  equicast-support#197, equicast-support#198, equicast#289. Originally its
  own `dispatch-isin-fix.yml`/`missing-isin-fix.yml`/
  `cleanup-merged-isin-branches.yml` workflow trio; folded into the shared
  listener/receiver/cleanup workflows once **config change** showed the
  shape generalized. The event name, payload shape, and every gate stayed
  identical through that move.

### Config change (stock/etf/fx/benchmark add/update/delete)

- **File**: no `sync-*-issue.sh` step here — the issue already exists.
  The support form (`backend/support/views.py`'s `SupportView.post`,
  category `ticker-request`) files it directly in `equicast-support`
  with the `ticker-request` label plus a `production`/`development`
  label, e.g. `[Ticker request] Ticker: BNC.L`
  (equicast-support#173 is a worked example).
- **Listen/Dispatch**: `.github/scripts/scenarios/config-change.sh` (on
  `equicast-support`) — identity is the `ticker-request` label; once
  matched, also requires a `production`/`development` label (which is how
  `ENVIRONMENT` is derived — never typed by the replying maintainer). The
  reply is parsed as `FIELD: value` lines in any order: `ASSET_CLASS`
  (required), `ACTION` (optional, defaults to `add`), `KEY` (optional —
  falls back to the issue's own `**Ticker:**` line), `ISIN`/`TAX_DOMICILE`
  (stock/etf), `SYMBOL` (benchmark). Fires the `config-change-requested`
  event.
- **Act**: `issue-automation-fix.yml`'s `config-change-requested` case arm +
  `.github/scripts/manage_config_entry.py` — applies the add/update/delete
  via `ruamel.yaml`'s round-trip mode (preserves comments/quoting/
  ordering) and opens a PR from a
  `config/<asset_class>-<environment>-<action>-<key>-<run_id>` branch.
  Deeper validation (idempotency, fx pairs having no overridable fields,
  etc.) lives in this script, not the dispatch gate — see its own
  docstring.
- **Clean up**: `cleanup-merged-automation-branches.yml`'s `config/` prefix.
- Supersedes an earlier `workflow_dispatch`-form design
  (equicast-support#6) in favor of this issue-driven shape, once it
  became clear the input (a support ticket) already existed as a
  GitHub issue rather than something a maintainer had to know to go
  trigger by hand.

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

**A reply never triggers anything** — check, in order: the commenter's
association is `OWNER`/`MEMBER`; the comment matches the scenario's exact
expected format; `EQUICAST_DISPATCH_TOKEN` exists and hasn't expired on
`equicast-support`; the issue satisfies the scenario's own identity check
in its `.github/scripts/scenarios/*.sh` file (for missing ISIN, that it's
a sub-issue of one of the tracked parent titles; for config change, that
it carries the `ticker-request` label plus a `production`/`development`
label). `dispatch_issue_automation.sh`'s own log (visible in the
`equicast-support` workflow run) says which scenario, if any, matched.

**Dispatch fires (visible under `equicast-support`'s workflow run) but no
PR appears in `equicast`** — check `issue-automation-fix.yml`'s run under
`equicast`'s Actions tab (one workflow now handles every scenario, so
there's only one place to look). For missing ISIN, the most likely cause
is `apply_isin_override.py` refusing to write because the ticker wasn't
found in the config path the issue named, or was found in more than one;
for config change, the most likely cause is `manage_config_entry.py`
refusing an `add` that already exists, an `update`/`delete` that doesn't,
or an `update` on an fx pair — by design, not a bug to silently work
around.

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

**A merged fix branch isn't deleted** — check
`cleanup-merged-automation-branches.yml` actually has a step gated on that
branch's prefix; a new scenario that forgot step 4 of "Adding a new
scenario" above will leave its branches lingering (harmlessly — just
noise).

## Security notes

- Every reply-triggered dispatch is gated on `author_association` — comment
  text on a public repo is otherwise attacker-controlled input. This gate
  lives once in `dispatch_issue_automation.sh`, ahead of every scenario,
  rather than being duplicated per scenario file.
- Cross-repo PATs are scoped to the single target repo and the minimum
  permission that repo's API calls need, not the whole `repo` scope
  org-wide.
- `repository_dispatch`-triggered workflows in `equicast` never trust a
  branch/ref carried in the payload — checkout is always pinned to
  `ref: main`, and the resulting PR's base is always `main`.
