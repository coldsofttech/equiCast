# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `frontend/public/brand/equicast-mark.png`: a 512x512 PNG export of the
  existing `equicast-mark.svg` (same gradient badge + Candlestick Spear
  icon), rasterized via `sharp`. Auth0's Application **Logo URL** field
  needs an image URI, not an SVG — once this is deployed and reachable at
  `<frontend_url>/brand/equicast-mark.png` (see `infra/main.tf`'s
  `frontend_bucket`/CloudFront distribution), that URL can be set as the
  `equiCast Web` Application's logo in the Auth0 dashboard.

### Changed

- Switched `fx-ingestion.yml`/`etf-ingestion.yml`/`stock-ingestion.yml`'s
  scheduled trigger from every 6 hours to once daily, Monday-Friday only, at
  22:00/22:15/22:45 UTC (`0 22 * * 1-5`/`15 22 * * 1-5`/`45 22 * * 1-5`) —
  after both the US (NYSE/NASDAQ) and UK (LSE) markets close, so each
  weekday's fetch gets that day's complete OHLC bar. yfinance's
  daily-interval history only changes once a trading day closes, so the
  previous 6-hourly schedule bought no real freshness, just repeated S3
  writes of the same data; both markets are shut every Saturday/Sunday, so
  the added day-of-week filter (`1-5`) skips those runs entirely rather than
  harmlessly re-fetching Friday's already-current close — it doesn't account
  for weekday market holidays (Christmas, Thanksgiving, etc.), which still
  trigger a run that harmlessly re-writes the last available close. The
  15m/30m chain offsets between the three pipelines are unchanged. Re-sized
  `infra/infracost-usage.prod.yml`'s `market_data_bucket` ingestion request
  counts for the new ~22-runs/month weekday cadence (down from 120 at
  6-hourly) — confirmed via a real `infracost breakdown` run: prod's
  `market_data_bucket` PUT cost drops from ~$30.01/month to ~$5.50/month
  (prod total ~$5.85/month, down from ~$30.36/month); dev is unaffected (it
  was never on the scheduled trigger to begin with — see that file's
  header).
- Split `infra/infracost-usage.yml` into `infra/infracost-usage.dev.yml` and
  `infra/infracost-usage.prod.yml` — `infracost.yml`'s two projects
  previously shared one usage file, so the "dev" and "prod" cost estimates
  were identical despite being very different deployments. Reworked the
  numbers to actually reflect that: dev models ~2 users, no scheduled
  ingestion (only ~12 manual `workflow_dispatch(environment=dev)` runs/month
  against today's small `*.dev.yaml` pair/ticker lists), for development and
  validation only; prod models ~50 active users and scheduled ingestion
  sized against an expected ~10,000-instrument US/UK stock+ETF universe
  (~9,000 stocks + ~1,000 ETFs, FX unchanged at 4 pairs) — a big jump from
  today's small `*.prod.yaml` placeholders (see the prior "Split fx/stock/
  etf ingestion configs" entry), reflected only in the cost model for now,
  not the actual config files. Backend Lambda/API Gateway/DynamoDB/
  `user_data_bucket` sizing now derives from an explicit per-session
  request-count breakdown (identity, accounts, portfolios, watchlists,
  holdings, transactions, market-data search — 15 HTTP calls/session, 20
  sessions/user/month) instead of a flat unexplained "500 MAU" guess, with
  dev/prod differing only in user count (2 vs. 50). `frontend_bucket`/
  CloudFront page-load traffic scales the same way; `backend_deploy_bucket`
  stays shared between dev/prod (deploy-frequency-driven, not
  user-count-driven).
- Tightened the three ingestion workflows' cron offsets from hours to
  minutes: `fx-ingestion.yml` still runs first on `0 */6 * * *`
  (00:00/06:00/12:00/18:00 UTC), but `etf-ingestion.yml` now runs 15 minutes
  later (`15 */6 * * *`) instead of 4 hours later, and `stock-ingestion.yml`
  now runs 30 minutes after ETF / 45 minutes after FX (`45 */6 * * *`)
  instead of 2 hours after FX — swapping the stock/ETF run order in the
  process (previously FX → stock → ETF, now FX → ETF → stock). Updated the
  offset comments/docs (`docs/{fx,stock,etf}-pipeline.md`, root `README.md`,
  `infra/infracost-usage.yml`) accordingly; the request-count estimates
  themselves are unchanged since all three still run 4 times/day.
- Split each ingestion pipeline's pair/ticker config into a `dev` and a
  `prod` file — `packages/fx/config/fx_pairs.{dev,prod}.yaml`,
  `packages/stock/config/stocks.{dev,prod}.yaml`,
  `packages/etf/config/etfs.{dev,prod}.yaml` — replacing the single
  `fx_pairs.yaml`/`stocks.yaml`/`etfs.yaml` each package previously had.
  `fx-ingestion.yml`/`stock-ingestion.yml`/`etf-ingestion.yml`'s `plan` job
  already resolved `dev`/`production` for which S3 bucket to upload to;
  it now resolves the environment *before* computing chunks and picks the
  matching config file for `equicast-{fx,stock,etf}-plan` too, so a manual
  dev run and the scheduled production run can diverge on which
  pairs/tickers get fetched, not just where the output lands. The `dev`
  file in each pair keeps the previously-existing list; the `prod` file is
  an exact copy for now (expand it independently as needed). Each
  Dockerfile's default `CMD` and `scripts/smoke_test.py`'s default
  `--config` now point at the `dev` file, since neither is used by the
  ingestion workflows (which always pass `--pairs-json`/`--tickers-json`
  explicitly) — only by ad-hoc local runs, where dev is the safer default.
- Frontend accounts UX fixes surfaced by manual review of Phase 1's Accounts
  & Pies work: (1) `Auth0ProviderWithNavigate.jsx` gains
  `cacheLocation="localstorage"` + `useRefreshTokens` — the SDK's default
  in-memory token cache was wiped on every hard reload, so refreshing any
  authenticated route (e.g. `/accounts`) bounced back to the sign-in screen
  even with a still-valid Auth0 session. (2) `DashboardPage`'s empty-state
  "Create an account" now opens the same `Drawer`+`AccountForm` right there
  instead of navigating to `/accounts` and needing a second click. (3)
  `AccountForm`'s description field is no longer marked `required` — the
  backend (`REQUIRED_CREATE_FIELDS` in `backend/accounts/views.py`) already
  allowed it blank. (4) `AccountForm` gains a `defaultCurrency` prop, seeded
  from the caller's own `profile.default_currency`, so a new account's
  currency field starts pre-filled with the user's own default instead of
  blank (editing an existing account still uses its own currency). (5)
  `Drawer.css`'s `max-width` is now `900px` (previously `440px`), applying
  to every drawer in the app. (6) `ConfirmDialog` now renders via `Modal`
  instead of `Drawer` — a delete confirmation is a single yes/no decision,
  not a form, so it no longer shares the wide side-drawer used for
  account/pie editing. (7) `AccountsListPage`'s top-of-page "New account"
  button is now hidden once the list has loaded and is empty (kept during
  the initial load to avoid a flash), leaving only the centered empty-state
  button, which duplicated it.

  Also added: `frontend/src/api/sessionCache.js` (thin sessionStorage
  read/write/clear helpers, tolerant of storage being unavailable) backs a
  reworked `useCurrentUser.js` and a new `useAccounts.js`, both of which now
  cache their GET result (`GET /api/identity/me/`, `GET /api/accounts/`) in
  `sessionStorage` and serve every later mount of the hook (Topbar,
  AccountsListPage, DashboardPage, ... each calls independently) from that
  cache instead of re-fetching; a module-level in-flight promise in each
  hook also collapses simultaneous first-mounts (e.g. Topbar + a page both
  mounting on first load) into a single request. `setProfile`/`setAccounts`
  write straight back to the cache, so a save from `SettingsModal` or a
  create/edit/delete from `AccountsListPage`/`DashboardPage` is what every
  later mount sees. `AccountDetailPage`/`PieDetailPage` load their own copy
  via `getAccount`/`getPie` rather than the shared list, so their own
  mutations (edit account, delete account, create/delete pie, allocation
  sync) now also patch the cached accounts list directly, keeping
  `/accounts`/`/dashboard` from showing stale data after a visit to a detail
  page. Both caches are cleared on sign-out (`UserMenu.jsx`'s
  `handleSignOut`) since `sessionStorage` survives the Auth0 logout/login
  redirect round trip on the same tab — without this a different account
  signing in on the same tab could briefly render the previous user's
  cached profile/accounts.
- `scripts/local-dev.ps1` gains `-Auth0ClientId` (defaulting to
  `$env:AUTH0_CLIENT_ID`, mirroring `-Auth0Domain`/`-Auth0Audience`'s
  existing `$env:AUTH0_DOMAIN`/`$env:AUTH0_AUDIENCE` defaults). With
  `-StartFrontend`, the three values are now exported as
  `VITE_AUTH0_DOMAIN`/`VITE_AUTH0_CLIENT_ID`/`VITE_AUTH0_AUDIENCE` into the
  spawned `npm run dev` process — Vite gives an already-set environment
  variable priority over `frontend/.env.local`, so the frontend's real
  Auth0 login flow now works out of the box against LocalStack without
  hand-creating that file. Previously only the backend's `AUTH0_DOMAIN`/
  `AUTH0_AUDIENCE` were wired up this way, leaving `RequireAuth` stuck on
  its "not configured" state for anyone running the script as documented.
  `docs/auth0-setup.md`'s Step 3 also gains a step easy to miss on a fresh
  tenant: the frontend Application needs an explicit **User-Delegated
  Access** grant against the API (Application Access tab) before
  `loginWithRedirect`'s `audience` param works — without it Auth0 returns
  `invalid_request: Client "..." is not authorized to access resource
  server "..."`, surfaced by the frontend as a generic "Something went
  wrong signing in" (`RequireAuth.jsx`).
- `backend-ci.yml`/`frontend-ci.yml` gain a `workflow_dispatch` trigger.
  Surfaced by merging #36 (frontend CD infra): that PR's changes lived
  entirely under `infra/`, `.github/workflows/deploy.yml`, and `docs/`, so
  neither CI workflow's path filter matched and neither ran — and since
  `deploy.yml` only triggers off `Backend CI`/`Frontend CI` completing via
  `workflow_run`, the frontend build never happened either, leaving the
  freshly-applied dev CloudFront distribution with nothing synced to its
  bucket. Any infra- or docs-only merge to `main` hits the same gap.
  `workflow_dispatch` lets a `main` run be kicked off by hand (Actions tab,
  or `gh workflow run "Frontend CI" --ref main`) to chain into `deploy.yml`
  without waiting on a matching code change.
- Fixed two related backend production-hardening gaps, both surfaced by
  manual testing of the Phase D accounts endpoints: (1) `infra/main.tf`'s
  `backend_lambda` never set `DJANGO_DEBUG`, so every deployed environment
  — dev and prod alike — silently fell back to `settings.py`'s
  `DEBUG="true"` default; an unhandled exception in prod would have
  rendered Django's full debug traceback page back to the caller instead
  of a generic 500. Now set explicitly per environment
  (`var.environment == "prod" ? "false" : "true"`) rather than left to the
  code default. (2) `backend/equicast_api/settings.py` gains
  `APPEND_SLASH = False`: a `POST`/`PATCH`/`DELETE` missing its trailing
  slash (e.g. `POST /api/accounts` instead of `/api/accounts/`) previously
  raised an unhandled `RuntimeError` — `CommonMiddleware` refuses to
  redirect a non-safe method with a body, since doing so risks dropping it
  — which combined with (1) meant that traceback was visible to the
  caller in prod too. Every `urls.py` pattern already ends in a trailing
  slash and every documented endpoint is written with one, so the
  redirect-on-`GET` behavior `APPEND_SLASH` exists for isn't useful here
  either; disabling it makes a missing trailing slash a plain `404` for
  every HTTP method instead. `backend/accounts/tests.py` gains a
  regression test asserting `404`, not `500`, for a slash-less `POST`.
- `terraform.yml` now sets `concurrency: { group: terraform-${{ github.ref }},
  cancel-in-progress: true }`. Since `development`/`production` gained
  required-reviewer approval, a run left `waiting` on an unapproved gate
  no longer gets superseded on its own — an older push's `apply-dev` could
  sit waiting indefinitely alongside a newer one for the same ref, cluttering
  the approval queue and risking someone approving stale infra. A newer push
  now cancels the older run for the same `github.ref` outright.
- Collapsed the `deploy-dev` GitHub Environment into `development`:
  `deploy.yml`'s `deploy-backend-dev`/`deploy-frontend-dev` now gate on
  `environment: development` (previously `deploy-dev`), the same
  environment `terraform.yml`'s `apply-dev` already used. `apply-dev` was
  previously ungated (`development` had no protection rules, relying only
  on the Infracost PR comment as a soft review); it now requires the same
  required-reviewer approval as the deploy jobs. Reason: an unreviewed PR
  merge to `main` was able to both apply infra changes and push a new
  backend build to dev fully automatically, with no approval gate at
  all — a real risk of an unintended AWS cost spike in dev.
  `docs/terraform-state-setup.md` and `docs/local-setup.md` updated to
  describe two gated GitHub Environments (`development`, `production`)
  instead of three.
- `market_data`'s `ProfileView`/`PricesView` now require Auth0 authentication
  (`authentication_classes = [Auth0JWTAuthentication]`,
  `permission_classes = [IsAuthenticated]`), matching `identity.MeView`.
  Previously these fell back to DRF's `AllowAny` default and were reachable
  without a Bearer token — `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`
  only *identifies* a caller, it doesn't by itself require authentication.
  `backend/market_data/tests.py` updated to mock the Auth0 JWT flow and
  assert 401 when no token is supplied.

### Added

- Frontend Phase 1 (Accounts & Pies): the first real domain pages, plus a
  core component library scoped to what they need — `frontend/src/components/core/`
  gains `Button`, `Card`, `Badge`, `Alert`, `Modal`/`ConfirmDialog`, the
  `TextField`/`SelectField`/`TextAreaField` trio (`Field.jsx`), and
  `EmptyState`, all built on the Phase 0 design tokens (no new colors or
  spacing values introduced). New `frontend/src/api/accounts.js`/`pies.js`
  wrap the backend's account/pie/pie-holdings endpoints
  (`backend/accounts/views.py`, `backend/pies/views.py`). Routes:
  `/accounts` (`AccountsListPage` — create/list, with `transaction_type`
  as a first-class field), `/accounts/:accountId` (`AccountDetailPage` —
  edit/delete the account, create/delete its pies, force-delete cascading
  into pies/holdings/transactions the same way the backend does), and
  `/accounts/:accountId/pies/:pieId` (`PieDetailPage` — edit/delete the
  pie, plus `AllocationEditor`, the add/remove/reallocate batch editor for
  `PUT /api/pies/<id>/holdings/`: local row state diffs against the
  loaded holdings to build the minimal `{add, remove, reallocate}` body,
  keeps `allocation_pct` as a string end-to-end so JS number handling
  never touches a value the backend parses via `Decimal`, and disables
  Save until the active rows sum to exactly 100%, mirroring
  `equicast_core.holdings`'s own invariant). `MenuBar` gains an optional
  per-item `to` — an item with one renders as a real `NavLink` (active by
  URL prefix, so a pie's page still shows "Portfolio" active); items
  without one keep Phase 0's local-only placeholder behavior
  (Watchlists/Search). `/` now redirects to `/accounts` instead of
  rendering the Phase 0 profile-card page, which is retired
  (`DashboardPage.jsx`); its one real proof — the signed-in user's
  `default_currency` from `useCurrentUser()` — and the log out button
  both move into `Topbar`, visible on every authenticated page instead of
  just one.
- Frontend Phase 0 (design tokens + app shell): `frontend/src/styles/tokens.css`
  ports [Resource Planner](https://github.com/coldsofttech/resource-planner)'s
  OKLCH design tokens as `--ec-*` custom properties — same values (Palette A,
  the "reused as-is" option from `docs/design/palette-options.html`), same
  type/spacing/radius/shadow scale, `data-theme` on `<html>` switching
  light/dark. `index.html` gains an inline bootstrap script that sets
  `data-theme` synchronously (localStorage, falling back to
  `prefers-color-scheme` once) before any stylesheet paints, so — like
  Resource Planner's own tokens.css — `tokens.css` only defines `:root`
  (light) and `[data-theme="dark"]`, no media-query fallback; a new
  `ThemeToggle` component (`frontend/src/components/shell/`) flips the
  attribute after that and persists the choice. New topbar + mega-menu
  app shell (`Topbar`, `MenuBar`, `AppShell`) — `MenuBar` collapses to a
  hamburger toggle under 640px, matching Resource Planner's own responsive
  behavior; no routing wired up yet, so menu items track an "active" item
  locally rather than navigating. New brand components
  (`frontend/src/components/brand/`): `Logo` (gradient badge + the
  "equi**Cast**" wordmark, CSS-driven — no image request, reads the same
  tokens so it flips with the theme for free) and `CandlestickSpearIcon`,
  the finalized mark from `docs/design/logo-concepts-round3-final.html`
  (three ascending OHLC candlesticks, the tallest candle's wick sharpened
  into a spearpoint) — see `docs/design/README.md` for the full brand
  decision history. `App.jsx` now renders the shell with placeholder page
  content instead of the old ticker-fetch smoke test; `App.test.jsx`
  rewritten to cover the wordmark, menu item selection, and the theme
  toggle instead. Routing, the API client, Auth0, and real domain pages
  are later phases.
- Frontend CD, S3 + CloudFront, no custom domain yet: `infra/main.tf`'s
  `frontend_bucket` module is stood up for real, but no longer as a public
  S3 static-hosting bucket (`static_site = true`) — it now stays fully
  private (default `block_public_access`), readable only by a new
  `aws_cloudfront_distribution.frontend` via Origin Access Control
  (`aws_cloudfront_origin_access_control.frontend` + a bucket policy
  scoped to that one distribution's `AWS:SourceArn`). SPA client-side
  routing (e.g. `/accounts/123`, no matching S3 key) is handled by two
  `custom_error_response` blocks rewriting 403/404 to `/index.html` with a
  200, since a private REST-endpoint origin has no `error_document` the
  way S3 website hosting did. No `aliases`/ACM/Route53 — `viewer_certificate`
  uses CloudFront's own shared `*.cloudfront.net` certificate, so the live
  URL is that generated hostname (`terraform output frontend_url`) until a
  domain is registered. `price_class = "PriceClass_100"` (US/Canada/Europe
  edge locations only, the cheapest class) and the AWS-managed
  `CachingOptimized` cache policy, rather than a hand-rolled one — a static
  SPA bundle needs no custom cache-key/TTL behavior. New outputs:
  `frontend_bucket_name`, `frontend_url`, and
  `frontend_cloudfront_distribution_id` (the last one isn't predictable
  the way the bucket name is — AWS generates it at apply time — so it has
  to be read after apply and set as each GitHub Environment's own
  `CLOUDFRONT_DISTRIBUTION_ID` variable; see
  `docs/terraform-state-setup.md`'s new Step 4).

  `deploy.yml`'s `deploy-frontend-dev`/`deploy-frontend-prod` jobs are
  uncommented and live (previously replaced by a `frontend-paused`
  placeholder pending exactly this work) — sync the build to S3, then
  `aws cloudfront create-invalidation --paths "/*"` so a deploy is visible
  immediately instead of waiting out the cache TTL (including a stale
  `index.html` referencing since-deleted hashed asset filenames).
  `estimate-frontend`'s job-summary cost estimate still only covers S3
  (storage + PUT), same as before; a note now points at
  `infra/infracost-usage.yml`'s new `aws_cloudfront_distribution.frontend`
  usage estimate (30GB/month transfer, sized off the same 50,000
  page-loads/month planning scenario `frontend_bucket`'s own estimate
  uses) for the CloudFront side, rather than trying to fold CloudFront's
  cache-hit-ratio-dependent cost into the same shell arithmetic.

  Note for whoever runs the first `apply-dev` after this: `equicast-frontend-dev`
  already exists in AWS from before `frontend_bucket` was commented out
  (see `docs/terraform-state-setup.md`), so that apply will destroy its
  `aws_s3_bucket_website_configuration` and re-block public access — both
  expected, not drift to investigate. Also unverified from this repo alone:
  whether the GitHub Actions deploy role (`secrets.AWS_ROLE_ARN`, not
  Terraform-managed here) already has `s3:PutObject`/`s3:DeleteObject` on
  the frontend buckets and `cloudfront:CreateInvalidation` — confirm
  before relying on `deploy-frontend-dev`/`-prod` to actually succeed.
- Frontend Phase 0 continued: routing, Auth0, a typed API client, and the
  brand SVG exports. `react-router-dom` (v7) — `App.jsx` is now just
  `<Routes>` (`/` -> the gated dashboard, `*` -> redirect to `/`) instead
  of rendering the shell directly; that moved to the new
  `pages/DashboardPage.jsx`. `@auth0/auth0-react` wired in via
  `Auth0ProviderWithNavigate` (inside `BrowserRouter` in `main.jsx`, so
  its `onRedirectCallback` can use `useNavigate`) and a new `RequireAuth`,
  which gates children behind `isAuthenticated` — an unauthenticated
  visitor gets a real `SignInScreen` (the brand `Logo` + tagline + a
  `loginWithRedirect` button), not a silent auto-redirect. No frontend
  Auth0 Application existed before this (`docs/auth0-setup.md` had
  explicitly deferred it) — new **Step 3** there covers registering one
  (SPA type, PKCE) and its Client ID becomes a new `AUTH0_CLIENT_ID` repo
  variable; the old Step 3 (wiring values into the repo) is now Step 4.
  If `VITE_AUTH0_*` isn't set, `RequireAuth` shows a clear "not
  configured" message without ever calling `useAuth0()`, rather than
  depending on the SDK's behavior against a missing Provider.

  Typed API client — JSDoc, not TypeScript (the frontend has no TS
  tooling, and introducing it was judged a bigger, harder-to-reverse
  change than this phase called for): `api/client.js` is a
  framework-agnostic `fetch` wrapper (bearer token injection, JSON
  encode/decode, an `ApiError` carrying `.status`), `api/useApi.js` binds
  Auth0's `getAccessTokenSilently` into it, and `api/identity.js` +
  `api/useCurrentUser.js` wire up the one real endpoint so far
  (`GET /api/identity/me/`) — `DashboardPage` renders its
  `default_currency` as an end-to-end proof of the whole chain (Auth0
  login -> access token -> Django -> DynamoDB -> back into React).

  Brand SVG exports (`frontend/public/brand/`): `equicast-mark.svg`
  (wired in as the favicon), `equicast-logo-light.svg`,
  `equicast-logo-dark.svg` — self-contained, hard-coded hex (not
  `oklch()`/CSS variables, which the email/other non-web contexts these
  are for can't rely on), matching the finalized Candlestick Spear icon.

  `MenuBar`/`ThemeToggle` gained their own direct tests (previously only
  covered indirectly through `App.test.jsx`, which now tests routing
  instead).

  Also closes the CD entry above's "known gap": `deploy-frontend-dev`/
  `-prod` each now build the frontend themselves, with that environment's
  own `VITE_API_BASE_URL` (from a new per-environment `API_URL` GitHub
  Environment variable, manually kept in sync with `terraform output
  backend_api_invoke_url` — see `docs/terraform-state-setup.md`'s Step 4,
  now also covering this alongside `CLOUDFRONT_DISTRIBUTION_ID`) and
  `VITE_AUTH0_CLIENT_ID`/`VITE_AUTH0_DOMAIN`/`VITE_AUTH0_AUDIENCE` baked
  in at build time, instead of `estimate-frontend` building once and both
  environments promoting that identical artifact — Vite inlines
  `import.meta.env.VITE_*` at build time, so one build can't correctly
  serve two environments with different backend URLs the way the backend
  Lambda zip can. `estimate-frontend` still builds once (with no
  environment config) purely for the pre-approval job-summary cost
  estimate; `deploy-frontend-prod`'s `needs: deploy-frontend-dev` is now
  ordering-only ("prod only after dev approves"), not an artifact
  promotion. Deliberately manual rather than automatic: the automatic
  alternative (`terraform.yml` running `gh variable set` after every
  apply) needs a personal access token with `Variables: write` — the
  default `GITHUB_TOKEN` workflows get can't call that API at all — which
  is a new credential to create/rotate for not much saved effort at this
  project's current scale.
- `scripts/local-dev.ps1`: a Windows PowerShell script that starts
  [LocalStack](https://www.localstack.io/) (S3 + DynamoDB), provisions
  `MARKET_DATA_BUCKET`/`USER_DATA_BUCKET`/`USER_PROFILES_TABLE`, and runs
  `manage.py runserver` against them — a fully local stand-in for the
  backend's AWS dependencies, with no real AWS account and (deliberately)
  no LocalStack account either. Needs no code change: every
  `equicast-core` client already calls plain
  `boto3.client(...)`/`boto3.resource(...)`, and the pinned
  `boto3>=1.35.9` honors the `AWS_ENDPOINT_URL_S3`/
  `AWS_ENDPOINT_URL_DYNAMODB` env vars the script sets to route those
  calls at LocalStack instead of real AWS. Pinned to
  `localstack/localstack:4.14.0`, deliberately not `:latest` — starting
  with the 2026.03.0 calendar-versioned release, even LocalStack's
  free-tier image requires a `LOCALSTACK_AUTH_TOKEN` (a free account) just
  to start, and `4.14.0` is the last semver release before that. `-Stop`
  and `-Reset` manage the container directly, and the backend run is
  wrapped in `try/finally` so Ctrl+C tears LocalStack down too rather than
  leaving it running detached. `-SeedMarketData` (optionally with
  `-FullLoad`) ingests all three asset classes via their own
  `equicast-fx`/`equicast-stock`/`equicast-etf` CLI and
  `packages/*/config/*.yaml`, uploads the output, and builds/uploads each
  asset class's catalog via `equicast-core-build-catalog` — clearing each
  pipeline's `./output` first, since `build_catalog_rows` globs everything
  under it and would otherwise mix in stale tickers left over from an
  earlier run with a different ticker list. Does not simulate Auth0
  (`Auth0JWTAuthentication` always talks to a real tenant — and every
  `/api/...` view requires it, `/api/market/...` included, not just
  `/api/accounts/...`/etc) or the Lambda/API Gateway deployment shape
  (runs the identical Django app via `manage.py runserver` instead, for
  instant reload instead of a zip rebuild/redeploy per change). See
  `docs/local-setup.md`'s new "Backend against LocalStack" section.
- `GET /api/market/search/`: ticker/name search, built on the
  `equicast_core.catalog`-backed `MarketDataClient.search()` (see below) —
  `?q=` required (at least 1 character), case-insensitive substring match
  against every scanned asset class's `ticker`/`name`. Optional
  `?asset_class=` narrows the scan to one of `fx`/`stock`/`etf`. Paginated
  (`?page=`, default `1`; `?page_size=`, default `50`, capped at `200`),
  returning `{count, page, page_size, total_pages, results}` — pagination
  is applied in `market_data/views.py` on top of `MarketDataClient.search()`'s
  already-sorted (by ticker) full match list, not pushed down into the
  client. `backend/market_data/tests.py` covers the new `SearchView`.
- Market data search catalog: a new `equicast_core.catalog` module (and
  `MarketDataClient.get_catalog`/`.search`) builds the read side of a
  ticker/name search — `catalog/<asset_class>.json`, one small
  `{ticker, name, type, current_price}` row per configured ticker,
  published by each ingestion pipeline rather than derived from
  `profile.parquet` on the fly, so search reads don't fan out into one
  S3 GetObject per ticker. `build_catalog_rows`/`upload_catalog` are
  asset-class- and pipeline-agnostic (ticker comes from the local
  `<asset_class>=<TICKER>/profile.parquet` directory name, not the
  profile itself, so it works uniformly for stock/etf profiles — which
  carry a `ticker`/`name` field — and fx profiles, which don't, using
  `from_currency`+`to_currency`/`description` instead), and also install
  as a CLI, `equicast-core-build-catalog --asset-class <fx|stock|etf>
  --output-dir <dir> --bucket <bucket>`. `stock-ingestion.yml`/
  `etf-ingestion.yml`/`fx-ingestion.yml` each gain a `build-catalog` job
  that runs after their `ingest` matrix completes: every `ingest` leg now
  also publishes its chunk's `profile.parquet` files as a 1-day build
  artifact, and `build-catalog` downloads+merges every leg's artifact into
  one local tree before running the CLI — necessary because a single
  ingest leg only ever processes its own chunk of the full ticker list
  (GitHub Actions caps a matrix at 256 legs), so no leg alone has enough
  to build a complete catalog. This needs no new S3 permission for the
  ingestion role (it reads the merged artifacts locally, then uploads with
  the `s3:PutObject` access `ingest` already had) or for the backend
  Lambda (already holds bucket-wide `s3:GetObject` on `market_data_bucket`).
  `packages/core/tests/test_catalog.py` covers the builder/CLI;
  `packages/core/tests/test_client.py` gained `get_catalog`/`search`
  coverage. `docs/stock-pipeline.md`/`etf-pipeline.md`/`fx-pipeline.md`
  updated for the new job and S3 layout addition.
- Phase D User-owned data (transactions): new `backend/transactions/`
  Django app exposing Auth0-authenticated CRUD for a holding's
  transactions — `GET`/`POST /api/transactions/` (`GET` takes optional
  `?holding_id=`/`?year=`/`?date_from=`/`?date_to=` filters),
  `GET`/`PATCH`/`DELETE /api/transactions/<holding_id>/<id>/`. Transactions
  only apply to stock/etf holdings under an account or a pie — never fx,
  never a watchlist holding. Backed by a new
  `equicast_core.TransactionsClient`
  (`packages/core/src/equicast_core/transactions.py`) — unlike every other
  Phase D domain (one JSON object per user), this one stores **one JSON
  object per holding**, at `transactions/<user_id>/<holding_id>.json`:
  every real access pattern here (holding-scoped list, a `SELL`'s
  cumulative-shares check, cascading a delete when a holding is removed)
  is already scoped to one holding, so this avoids rewriting a whole-user
  blob on every write — the trade-off is that listing *every* transaction
  for a user (no `?holding_id=`) has to enumerate and read every holding's
  file instead of one read. The detail routes are nested under
  `holding_id` for the same reason: an id-only lookup would otherwise mean
  scanning every holding file for the user. Accounts gain a required
  `transaction_type` field (`AVERAGE` or `TRANSACTION`) governing how
  every holding under that account — directly, or via one of its pies —
  records transactions: `AVERAGE` is a single mutable snapshot per holding
  (`no_of_shares`, `average_price`, no date — `PATCH`-able, since it's
  corrected over time rather than logged); `TRANSACTION` is an immutable
  log of `BUY`/`SELL` events (`no_of_shares`, `price`, `date`, `type`),
  any number per holding (up to `MAX_TRANSACTIONS_FOR_HOLDING`, default
  `500`, `-1` to disable — this is a safety limit against one holding's
  file growing unbounded, not a cost control, since `TRANSACTION`-mode
  history only ever grows), with a `SELL` rejected
  (`InsufficientSharesError`) if it would take the holding's net recorded
  shares (summed in recorded order, not date order) below zero. Every
  record has the same stable six-key shape regardless of mode, `null`
  where not applicable — the same reasoning `HoldingsClient` uses for its
  parent-id fields; an `AVERAGE` record's `date` is always `null`, so it
  never matches the list endpoint's `year`/`date_from`/`date_to` filters.
  `transaction_type` is locked once the account has any transactions
  recorded under it (`accounts/views.py`'s `PATCH` now rejects the field
  with `409` in that case, checked via a new
  `TransactionsClient.has_transactions_for_holdings` targeted existence
  check rather than a full per-user scan). A holding can be created with
  its first transaction in the same request (`POST /api/holdings/`'s
  optional nested `"transaction"` field, validated before the holding is
  written and rolled back via `delete_holding` if the paired
  `create_transaction` fails — S3 has no cross-object transaction of its
  own) or afterwards via a separate `POST /api/transactions/`; pie-scoped
  holdings (created via `PUT /api/pies/<id>/holdings/`) only support the
  latter. Deleting a holding, or force-deleting a pie/account, now
  cascades into `delete_transactions_for_holdings`, which deletes each
  matching holding's S3 object outright (no concurrent writer to race once
  the holding itself is gone) rather than rewriting it to an empty list.
  For now this only stores what the caller provides — no computed average
  price, dividends, or returns. `MAX_TRANSACTIONS_FOR_HOLDING` is sourced
  from a new `infra/variables.tf`'s `max_transactions_for_holding`
  Terraform variable, passed by `terraform.yml`'s `apply-dev`/`apply-prod`
  jobs as
  `-var max_transactions_for_holding=${{ vars.MAX_TRANSACTIONS_FOR_HOLDING }}`.
  New Terraform: the `backend_lambda` IAM policy gains
  `s3:GetObject`/`s3:PutObject`/`s3:DeleteObject` on
  `<user_data_bucket_arn>/transactions/*` (mirroring the
  accounts/pies/watchlists/holdings statements, its own review, plus
  `s3:DeleteObject` for the per-holding-object cascade delete above), and
  the shared `s3:ListBucket` statement's `s3:prefix` condition now also
  covers `transactions/*`. No new bucket — reuses `user_data_bucket`.
  `packages/core/tests/test_transactions.py` covers the client;
  `packages/core/tests/test_accounts.py` updated for the new required
  `transaction_type` field.
- Phase D User-owned data (holdings): new `backend/holdings/` Django app
  exposing Auth0-authenticated CRUD for a user's holdings, nested under
  exactly one of an account, a pie, or a watchlist —
  `GET`/`POST /api/holdings/` (`GET` takes at most one of `?account_id=`/
  `?pie_id=`/`?watchlist_id=`), `GET`/`DELETE /api/holdings/<id>/` (no
  `PATCH` — a holding's fields are immutable; to change one, delete and
  re-add). Backed by a new `equicast_core.HoldingsClient`
  (`packages/core/src/equicast_core/holdings.py`), same shape as
  `PiesClient`/`WatchlistsClient` — one JSON object per user at
  `holdings/<user_id>.json` (`{"holdings": [...]}`), S3 conditional writes,
  conflict-retry loop. Each holding is `{id (uuid4), ticker, asset_class,
  account_id, pie_id, watchlist_id, timestamp}`, with exactly one of the
  three parent fields set and the other two `null` (a stable shape rather
  than sometimes-absent keys). `ticker`/`asset_class` (`fx`/`stock`/`etf`)
  must have market data in equicast-market-data-* — validated via
  `MarketDataClient.get_profile`, the same client `market_data/views.py`'s
  `ProfileView` uses — before a holding is allowed to exist; the frontend's
  ticker search (a later phase) is expected to resolve `asset_class` for
  the caller, the same way it already has to pick which asset class a
  search result came from. A ticker can't repeat within the same parent
  instance (`HoldingAlreadyExistsError`, `409`) but can freely repeat
  across different parents/instances (two different pies, a pie and a
  watchlist, ...). `account_id`/`watchlist_id` ownership is validated the
  same way `pies/views.py` validates a pie's `account_id` — these are
  free-form string fields on the holding record, not structurally scoped
  to the caller, so `holdings/views.py` checks them against
  `AccountsClient.list_accounts`/`WatchlistsClient.list_watchlists` before
  creating.

  Pie holdings are different: a pie represents a 100%-allocated slice of an
  account, so each pie holding also carries `allocation_pct`, and the sum
  across a pie's holdings must always be exactly 100% once it holds
  anything (an empty pie is a valid, unconstrained state) — not just
  capped, exact. A standalone single-item create/delete can't maintain
  that invariant once a pie already holds something, so pie holdings never
  go through the plain `POST`/`DELETE` above (both explicitly reject
  `pie_id`, returning `400` and pointing at the endpoint below instead).
  `PieHoldingsView` (new: `pies/views.py`,
  `PUT /api/pies/<id>/holdings/`) is the only way to mutate a pie's
  holdings — one batch request can add tickers (with their `allocation_pct`),
  remove existing holdings by id, and reallocate existing holdings'
  `allocation_pct`, all together. Backed by a new
  `HoldingsClient.sync_pie_holdings`, which validates the *resulting* state
  before writing anything — every `add` ticker has market data and isn't
  already held in the pie (existing or duplicated within `add` itself),
  every `remove`/`reallocate` id actually belongs to the pie
  (`HoldingNotFoundError`, `400`), the resulting count stays under
  `MAX_HOLDINGS_FOR_PIE` (`HoldingLimitExceededError`, `409`), and the
  resulting non-empty holdings sum to exactly 100%
  (`AllocationError`, `400`) — parsed via `Decimal` rather than `float` to
  avoid reintroducing binary floating-point sum errors right before the
  exactness check they exist to avoid. Any failure writes nothing; success
  is one S3 conditional put, same conflict-retry pattern as everywhere else
  in this domain.

  `create_holding`/`sync_pie_holdings` enforce three separate per-parent
  caps — `MAX_HOLDINGS_FOR_ACCOUNT` (100, direct account holdings only, not
  pie-scoped ones), `MAX_HOLDINGS_FOR_PIE` (50), `MAX_HOLDINGS_FOR_WATCHLIST`
  (20) — each configurable the same way `MAX_ACCOUNTS`/`MAX_PIES`/
  `MAX_WATCHLISTS` are: env vars sourced from new
  `infra/variables.tf` Terraform variables (`max_holdings_for_account`/
  `max_holdings_for_pie`/`max_holdings_for_watchlist`), passed by
  `.github/workflows/terraform.yml`'s `apply-dev`/`apply-prod`. New
  Terraform: the backend Lambda's IAM policy gains a statement scoped to
  `s3:GetObject`/`s3:PutObject` on `<user_data_bucket_arn>/holdings/*`
  (mirroring the accounts/pies/watchlists statements, its own review), and
  the existing `s3:ListBucket` statement's `s3:prefix` condition now also
  covers `holdings/*`. No new bucket — reuses `user_data_bucket`.

  Every other Phase D domain gained holdings-awareness: `pies/views.py`'s
  `PieDetailView.get` now nests `holdings`; its `delete` gained the same
  `409`-unless-`?force=true` guard `AccountDetailView.delete` already had
  for pies, cascading into a new `HoldingsClient.delete_holdings_for_pies`
  bulk method. `watchlists/views.py`'s `WatchlistDetailView.get`/`delete`
  gained the identical treatment, via `delete_holdings_for_watchlist`.
  `accounts/views.py`'s `AccountListView.get` (previously bare) and
  `AccountDetailView.get` now both return each account with its `pies`
  (each carrying its own `holdings`) and the account's own direct
  `holdings` — still a constant number of S3 reads regardless of how many
  accounts/pies/holdings exist, since `PiesClient`/`HoldingsClient` each
  return their whole per-user JSON object in one read and the nesting is
  grouped in memory (`accounts/views.py`'s new `_nest_pies_and_holdings`
  helper). `AccountDetailView.delete`'s guard now also blocks on direct
  account holdings (pie-nested holdings are already covered transitively
  by the existing "has pies" check); its force path cascades through both,
  via `delete_holdings_for_pies`/`delete_holdings_for_account`. As before,
  this is a best-effort check-then-act guard, not a cross-object
  transaction — matching every other guarantee in this domain.

  `packages/core/tests/test_holdings.py` (32 tests) and
  `backend/holdings/tests.py` cover the client and view layer, including
  per-parent cap/uniqueness enforcement, the pie batch endpoint's
  validation paths, and a concurrent-write-conflict regression test
  mirroring `test_pies.py`'s; `backend/accounts/tests.py`,
  `backend/pies/tests.py`, and `backend/watchlists/tests.py` gained
  coverage for the new nesting/force-delete behavior.
  `docs/local-setup.md`, `backend/README.md`, and `packages/core/README.md`
  updated with the new endpoints/client.
- Phase D User-owned data (watchlists): new `backend/watchlists/` Django app
  exposing Auth0-authenticated CRUD for a user's watchlists —
  `GET`/`POST /api/watchlists/`, `GET`/`PATCH`/`DELETE /api/watchlists/<id>/`.
  Backed by a new `equicast_core.WatchlistsClient`
  (`packages/core/src/equicast_core/watchlists.py`), same shape as
  `AccountsClient` — one JSON object per user at `watchlists/<user_id>.json`
  (`{"watchlists": [...]}`), S3 conditional writes for optimistic
  concurrency, conflict-retry loop. Each watchlist is `{id (uuid4), name,
  description, created_at, updated_at}`; holdings within a watchlist aren't
  modeled yet — that's a later phase. Unlike pies, a watchlist is
  **user-level, not nested under an account** — a user shouldn't need to
  create an account just to watchlist a few holdings — so there's no
  `account_id` field, no ownership validation against `AccountsClient`, and
  `accounts/views.py` is untouched (no nesting on `AccountDetailView.get`,
  no delete guard: deleting an account has no bearing on a user's
  watchlists). `create_watchlist` enforces a 5-watchlists-**per-user** cap
  via `WatchlistLimitExceededError` (surfaced as `409`);
  `get_watchlist`/`update_watchlist`/`delete_watchlist` raise
  `WatchlistNotFoundError` for an unknown id (surfaced as `404`). The cap is
  configurable the same way `MAX_ACCOUNTS`/`MAX_PIES` are: a new
  `MAX_WATCHLISTS` env var (default `5`), sourced from a new
  `infra/variables.tf`'s `max_watchlists` Terraform variable, passed by
  `.github/workflows/terraform.yml`'s `apply-dev`/`apply-prod` via
  `-var max_watchlists=${{ vars.MAX_WATCHLISTS }}`. New Terraform: the
  backend Lambda's IAM policy gains a statement scoped to
  `s3:GetObject`/`s3:PutObject` on `<user_data_bucket_arn>/watchlists/*`
  (mirroring the accounts/pies statements, its own review), and the
  existing `s3:ListBucket` statement's `s3:prefix` condition now also
  covers `watchlists/*`. No new bucket — reuses `user_data_bucket`.
  `packages/core/tests/test_watchlists.py` (12 tests) and
  `backend/watchlists/tests.py` (14 tests) cover the client and view layer,
  mirroring `test_accounts.py`/`accounts/tests.py`'s per-user cap coverage
  and concurrent-write-conflict regression test. `docs/local-setup.md`,
  `backend/README.md`, and `packages/core/README.md` updated with the new
  endpoints/client.
- Phase D User-owned data (pies): new `backend/pies/` Django app exposing
  Auth0-authenticated CRUD for a user's pies, nested under one of their
  accounts — `GET`/`POST /api/pies/` (`GET` takes an optional
  `?account_id=` filter), `GET`/`PATCH`/`DELETE /api/pies/<id>/`. Backed by
  a new `equicast_core.PiesClient` (`packages/core/src/equicast_core/pies.py`),
  same shape as `AccountsClient` — one JSON object per user at
  `pies/<user_id>.json` (`{"pies": [...]}`), S3 conditional writes for
  optimistic concurrency, conflict-retry loop. Each pie is
  `{id (uuid4), account_id, name, description, created_at, updated_at}`;
  holdings and their target allocation within a pie aren't modeled yet —
  that's a later phase, so no allocation-validation logic exists to sit
  unused in the meantime. `account_id` is immutable after creation (a pie
  doesn't move between accounts). `create_pie` enforces a
  20-pies-**per-account** cap (not per user) via `PieLimitExceededError`
  (surfaced as `409`); `get_pie`/`update_pie`/`delete_pie` raise
  `PieNotFoundError` for an unknown id (surfaced as `404`).
  `pies/views.py` validates on create that `account_id` is one of the
  caller's own accounts (via `AccountsClient.list_accounts`) before
  creating a pie against it — `PiesClient` itself stays generic/
  self-contained like `AccountsClient` and doesn't know about accounts;
  ownership is a view-layer concern, the same place the existing
  required-field checks already live. `accounts/views.py`'s
  `AccountDetailView` gains a `GET`, returning an account's own fields
  plus its nested `pies` (via `PiesClient.list_pies(user_id,
  account_id=...)`); `AccountsClient` gains `get_account` to back it.
  `AccountDetailView.delete` now refuses to delete an account that still
  has pies under it (`409`, listing them via the same `list_pies` call)
  unless the caller passes `?force=true`, in which case it removes those
  pies first (`PiesClient.delete_pies_for_account`, a new bulk-delete
  method — one read/write for the whole account rather than looping
  `delete_pie` per pie) before deleting the account itself. This is a
  best-effort check-then-act guard, not a cross-object transaction —
  accounts and pies are two separate S3 objects with no atomic multi-object
  write available, matching every other guarantee in this domain (S3's
  conditional writes are already only per-object).
  New Terraform: the backend Lambda's IAM policy gains a statement scoped
  to `s3:GetObject`/`s3:PutObject` on `<user_data_bucket_arn>/pies/*`
  (mirroring the accounts statement, its own review), and the existing
  `s3:ListBucket` statement's `s3:prefix` condition now covers both
  `accounts/*` and `pies/*` (still one shared statement — `ListBucket` is
  bucket-level, so it can't be scoped to a resource ARN per domain the way
  `GetObject`/`PutObject` are). No new bucket — reuses `user_data_bucket`.
  `packages/core/tests/test_pies.py` (16 tests) and `backend/pies/tests.py`
  (17 tests) cover the client and view layer, including per-account (not
  per-user) cap enforcement and a concurrent-write-conflict regression test
  mirroring `test_accounts.py`'s; `backend/accounts/tests.py` (now 17 tests)
  gained coverage for the new `DELETE`-with-pies `409`/`?force=true` paths.
  `docs/local-setup.md`, `backend/README.md`, and `packages/core/README.md`
  updated with the new endpoints/client.
- The accounts/pies caps are now configurable per deployment instead of
  hardcoded: `AccountsClient`/`PiesClient` take `max_accounts`/
  `max_pies_per_account` constructor args (still defaulting to the prior
  hardcoded `MAX_ACCOUNTS`/`MAX_PIES` values, 5/20), and
  `backend/equicast_api/settings.py` sources them from new `MAX_ACCOUNTS`/
  `MAX_PIES` env vars (defaulting the same way if unset). `infra/main.tf`
  plumbs these into the backend Lambda from two new Terraform variables
  (`infra/variables.tf`'s `max_accounts`/`max_pies`, also defaulted to 5/20
  so `terraform plan` — which runs outside any GitHub Environment — still
  works without them). `.github/workflows/terraform.yml`'s `apply-dev`/
  `apply-prod` pass the real values via `-var max_accounts=${{
  vars.MAX_ACCOUNTS }} -var max_pies=${{ vars.MAX_PIES }}`, reading each
  from that job's own GitHub Environment (`development`/`production`) —
  product can now retune either cap per environment from GitHub's UI, no
  code change or release required. `packages/core/tests/test_accounts.py`
  gained coverage for `get_account` and a custom `max_accounts`.
- Phase D User-owned data (accounts): new `backend/accounts/` Django app
  exposing Auth0-authenticated CRUD for a user's investment accounts —
  `GET`/`POST /api/accounts/`, `PATCH`/`DELETE /api/accounts/<id>/`. Backed
  by a new `equicast_core.AccountsClient`
  (`packages/core/src/equicast_core/accounts.py`), which stores each user's
  accounts as a single JSON object in S3 at `accounts/<user_id>.json`
  (`{"accounts": [...]}`) rather than DynamoDB — DynamoDB stays reserved for
  the small, identity-keyed profile record (`UserProfileClient`), while
  every other user-owned domain (accounts now; portfolios/watchlists/
  holdings later) lives as JSON in S3, one object per user per domain. Each
  account record is `{id (uuid4), name, description, account_type,
  currency, created_at, updated_at}`; `account_type` is free text for now
  (no server-side enum) — the frontend is expected to offer a dropdown of
  suggested values. `create_account` enforces the product-defined
  5-accounts-per-user cap, raising `AccountLimitExceededError` (surfaced by
  the view as `409`); `update_account`/`delete_account` raise
  `AccountNotFoundError` for an unknown id (surfaced as `404`). Reads/writes
  use S3's conditional-write support (`IfNoneMatch="*"` on first create,
  `IfMatch=<etag>` thereafter) for the same optimistic-concurrency guarantee
  `UserProfileClient` gets from DynamoDB's `ConditionExpression` — S3 has no
  per-field conditional update, only whole-object conditional puts, so a
  write that loses the race (another tab/process wrote first) is retried
  against the now-current state rather than silently clobbering it. Requires
  `boto3>=1.35.9` (bumped from `>=1.34` in both `packages/core/pyproject.toml`
  and `backend/pyproject.toml`) — S3 conditional writes were only added to
  botocore in 1.35.2.
  New Terraform: `infra/main.tf`'s `user_data_bucket` module provisions
  `equicast-user-data-<env>` — deliberately a new, separate bucket from
  `market_data_bucket` (a read-only ingestion-pipeline artifact store; the
  Lambda only holds `s3:GetObject` on it) rather than folding accounts in
  there, to avoid broadening that bucket's IAM footprint and blurring two
  unrelated lifecycles. One bucket is shared across all of Phase D's
  domains, with domain-prefixed keys (`accounts/<user_id>.json`, ...)
  rather than a bucket per domain. The backend Lambda's IAM policy gains a
  statement scoped to `s3:GetObject`/`s3:PutObject` on
  `<bucket_arn>/accounts/*` specifically (not the whole bucket), so each
  future domain gets its own reviewed statement as it's added, plus a
  separate `s3:ListBucket` statement on the bucket itself (a bucket-level
  action, so it can't be scoped to `.../accounts/*` the way `GetObject`/
  `PutObject` are — a `StringLike` condition on `s3:prefix` keeps it
  restricted to the `accounts/` domain instead). `ListBucket` is required
  alongside `GetObject` for a key that might not exist yet: without it, S3
  can't distinguish this role from a caller with no rights to know whether
  the object exists at all, so a first-time user's `GetObject` on their
  not-yet-created `accounts/<user_id>.json` returned `AccessDenied` instead
  of the `NoSuchKey` `AccountsClient._load()` catches to mean "no accounts
  yet". New `USER_DATA_BUCKET` env var (no default, same "fail loudly"
  precedent as `MARKET_DATA_BUCKET`/`USER_PROFILES_TABLE`) plumbed through
  `infra/main.tf`'s `backend_lambda` module and a new
  `user_data_bucket_name` output. `infra/infracost-usage.yml` gained a
  usage estimate for the new bucket (rough, same "nothing calls this yet"
  caveat as `user_profiles_table`'s entry, sized against the same 500-MAU
  planning scenario).
  `packages/core/tests/test_accounts.py` (9 tests) and
  `backend/accounts/tests.py` (10 tests) cover the client and view layer
  respectively, including a test that simulates a concurrent write losing
  the conditional-write race and asserts the retry lands on the merged
  state rather than raising or overwriting it. `docs/local-setup.md`,
  `backend/README.md`, and `packages/core/README.md` updated with the new
  endpoints/client/env var.
- Phase C Identity: Auth0-based authentication for the backend.
  `equicast_core.UserProfileClient` (`packages/core/src/equicast_core/user_profiles.py`),
  a DynamoDB client mirroring `MarketDataClient`'s shape, reads/upserts one
  item per user (`user_id`, `default_currency`) in the `user-profiles`
  table `infra/main.tf` already provisioned but hadn't wired up yet.
  `get_or_create_profile()` creates a new profile with
  `default_currency="GBP"` (equiCast's app-level default, not USD) on first
  login, via a conditional put (`attribute_not_exists(user_id)`) so a
  concurrent first login can't clobber a profile the user has already
  started customizing — the loser re-fetches and returns the winning write.
  The DynamoDB `Table` resource is resolved lazily (a `cached_property`,
  not in `__init__`), unlike `MarketDataClient`'s eager S3 client, since
  `resource("dynamodb").Table(name)` validates its name argument
  immediately and would otherwise blow up at Django's URLconf import time
  whenever `USER_PROFILES_TABLE` is unset (e.g. local dev without it
  configured). `packages/core`'s scope/README/description widened
  accordingly (was S3-market-data-specific); its dev deps gained
  `moto[s3]` → `moto[s3,dynamodb]` for `tests/test_user_profiles.py`.
  New `backend/identity/` Django app: `Auth0JWTAuthentication` (a DRF
  `BaseAuthentication` verifying RS256 access tokens against Auth0's JWKS
  via `PyJWKClient`, checking issuer/audience/expiry, keyed by the token's
  `sub` claim) and `GET /api/identity/me/` (`IsAuthenticated`, calls
  `get_or_create_profile(request.user.user_id)`), registered as
  `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` — it only *identifies*
  a caller when a Bearer token is present (returns `None`, not an error,
  when the header is missing), so `market_data`'s existing unauthenticated
  endpoints are unaffected. Still one Lambda: `identity` is just another
  Django app sharing `market_data`'s existing `backend_lambda`/API Gateway,
  not a new deployment unit. New settings `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`,
  `USER_PROFILES_TABLE` (no defaults, same "fail loudly" precedent as
  `MARKET_DATA_BUCKET`); new dependency `pyjwt[crypto]>=2.8`.
  `infra/main.tf`'s `backend_lambda` environment now also includes
  `USER_PROFILES_TABLE` (the table name was already exposed by
  `module.user_profiles_table` but never consumed) and
  `AUTH0_DOMAIN`/`AUTH0_AUDIENCE` (new `var.auth0_domain`/`var.auth0_audience`
  in `infra/variables.tf`, required inputs — Auth0 isn't Terraform-managed,
  see `docs/auth0-setup.md`). `terraform.yml`'s `plan`/`apply-dev`/`apply-prod`
  steps pass them as `-var auth0_domain=${{ vars.AUTH0_DOMAIN }} -var
  auth0_audience=${{ vars.AUTH0_AUDIENCE }}` — plain GitHub repo
  **variables**, not secrets: neither value is sensitive (the domain is a
  public JWKS hostname, the audience is embedded in every issued token's
  `aud` claim and the frontend's own Auth0 config), and this phase
  introduces no real secret at all since the backend only verifies tokens,
  never authenticates itself to Auth0. New `docs/auth0-setup.md` (mirrors
  `docs/aws-github-oidc-setup.md`'s style) covering tenant/API creation and
  end-to-end verification via a test token.
- `equicast-events` (`packages/events/`): standalone, generic package for
  corporate events (earnings reports, analyst rating changes, stock splits)
  on any yfinance equity-like symbol, built the same way as
  `equicast-dividends`/`equicast-metrics`. `equicast-stock`'s CLI now writes
  `stock=<TICKER>/year=<YYYY>/events.parquet` alongside price/dividend,
  combining all three event types into one file per year via an
  `event_type` discriminator column.
- `equicast-datafeed`: `get_earnings_dates`, `get_upgrades_downgrades`, and
  `get_splits`, backing `equicast-events`.
- Educational-use disclaimers, documented in each package's README
  (`equicast-datafeed`, `equicast-fx`: yfinance-sourced data, not financial
  advice; `equicast-metrics`: calculated by equicast, validate accuracy
  independently) and shown once per process as a console warning —
  `DatafeedClient`/`FXClient` share one disclaimer (deduped by message text,
  via a new `equicast_datafeed.warn_once` helper, so constructing many of
  either doesn't repeat it), `MetricsClient` shows its own. Falls back to
  Python's logging "handler of last resort" (plain stderr output) when
  nothing else has configured a handler, so it's visible either way.
- Initial project scaffold with `equicast`, a core Python package (yfinance
  ingestion, Parquet storage) as the root of a uv workspace.
- Django REST backend (`backend/`) exposing market data at
  `/api/market-data/<ticker>/`, depending on `equicast` via the uv workspace.
- React (Vite) frontend (`frontend/`) with a minimal UI for fetching ticker
  history.
- Terraform configuration (`infra/`) for AWS: S3 market-data bucket, S3
  static-site bucket for the frontend, and an ECR repository for the backend
  image.
- GitHub Actions workflows: backend CI (ruff, mypy, pytest), frontend CI
  (eslint, vitest, build), Terraform plan/apply, and deploy (ECR push + S3
  sync).
- Pre-commit hooks (`.pre-commit-config.yaml`) covering ruff, mypy, and
  pytest (unit) for the core package and Django backend, plus eslint and
  vitest (unit) for the React frontend.
- `equicast-datafeed` (`packages/datafeed/`): standalone package providing a
  resilient yfinance client with rate limiting and retry-with-backoff,
  reusable by any future market-data package.
- `equicast-fx` (`packages/fx/`): standalone, class-based package for
  extracting FX pair profiles (`FXClient(from_currency, to_currency).profile()`),
  returning from/to currency, exchange, region, description, last updated,
  source, day open/high/low/close/average, year open/high/low/close/average
  (trailing 52-week window, `year_open` from a `history(period="1y")` call,
  `*_average` as the high/low midpoint), and the 50-/200-day moving averages.
  Configured via `packages/fx/config/fx_pairs.yaml` (GBP/USD, USD/GBP,
  GBP/EUR, EUR/GBP by default); its CLI writes one Parquet file per pair to
  `fx=<PAIR>/profile.parquet`, reading pairs from that config or a
  `--pairs-json` string, with `--max-workers`/`--max-calls`/`--period-seconds`
  to control concurrency and the shared rate limit.
- `equicast-fx-plan`: a second CLI entry point that splits the configured FX
  pairs into chunks (capped at 256 — GitHub's per-workflow matrix job limit),
  growing the chunk size rather than dropping pairs if needed.
- `packages/fx/Dockerfile`, built and pushed to GHCR as a private image via
  the new `fx-image.yml` workflow.
- `fx-ingestion.yml`: runs every 6 hours (and on demand) as two jobs — a
  `plan` job computing chunks via `equicast-fx-plan`, and an `ingest` matrix
  job (one leg per chunk, `max-parallel: 20`) that pulls the `equicast-fx`
  image, passes its chunk via `--pairs-json`, and uploads the resulting
  Parquet files to `s3://equicast-market-data-<env>/fx=<PAIR>/`. Scales to
  large pair lists both across legs (separate runners/IPs) and within each
  container (concurrent fetches under a shared rate limit).
- `fx-ci.yml`: ruff, mypy, and pytest for `equicast-datafeed` and
  `equicast-fx`.
- `FXClient.prices(full_load=False)`: returns one daily OHLC record per
  trading day (from/to currency, date, open, high, low, close, average,
  last updated, source). Defaults to the current year (`period="ytd"`);
  `full_load=True` fetches the pair's entire yfinance history instead
  (`period="max"`). The CLI writes one `fx=<PAIR>/year=<YYYY>/price.parquet`
  per year covered, and a `--full-load` flag controls the same behavior;
  `fx-ingestion.yml` exposes it as a `workflow_dispatch` boolean input.
  Profile and prices are fetched as independent concurrent tasks per pair
  (submitted to the same worker pool as `--max-workers`), sharing one
  `FXClient`/`DatafeedClient` so the configured rate limit still applies
  across both.
- `docs/local-setup.md` and `docs/fx-pipeline.md`: the technical setup and
  deployment/execution details that used to live in the README, which is now
  scoped to the functional description of what equiCast produces.
- `packages/fx/scripts/smoke_test.py`: a manual QA tool (not part of the
  `pytest` suite) that runs `FXClient.profile()`/`.prices()` against live
  Yahoo Finance data for a set of pairs (defaults to `config/fx_pairs.yaml`,
  or `--pairs FROM:TO,...`), printing JSON to stdout or writing real Parquet
  via `--format parquet --out <dir>`, with `--full-load` for prices. Works
  the same way inside the Docker image via an entrypoint override;
  documented in `docs/fx-pipeline.md`.
- `equicast-metrics` (`packages/metrics/`): standalone, generic package for
  risk/performance metrics on any yfinance symbol — an FX pair (`GBPUSD=X`)
  or a stock ticker (`AAPL`) alike. `MetricsClient(symbol).metrics()` returns
  `volatility`, `sharpe_ratio`, `max_drawdown` (all trailing 1-year, Sharpe
  assuming a 0% risk-free rate), `cagr_1y`/`2y`/`3y`/`5y`/`10y` (`None` where
  there isn't enough history), `last_updated`, and `source`. Checks yfinance
  first per field (only `cagr_1y` has an equivalent, `fiftyTwoWeekChangePercent`)
  before calculating; guards against a still-forming trading day's `NaN`
  close price poisoning every downstream calculation.
- `equicast-fx` now also writes `fx=<PAIR>/metrics.parquet` per pair (from/to
  currency plus the `equicast-metrics` fields above), fetched as a third
  concurrent task alongside profile and prices. Unaffected by `--full-load`
  (metrics always looks back as far as `cagr_10y` needs, regardless).
- `fx-ci.yml` and `.pre-commit-config.yaml` now also lint/type-check/test
  `equicast-metrics`; `packages/fx/Dockerfile` copies it into the image.
- `equicast_datafeed.round_value`/`DECIMAL_PRECISION` (8): a shared
  decimal-precision policy for every numeric field `equicast-fx` and
  `equicast-metrics` compute or re-emit, cutting off float64 representation
  noise (e.g. `1.3504753112792969` → `1.35047531`) while staying above FX's
  ~5-decimal pipette precision and the ~4-6 decimals meaningful for
  risk/performance ratios. Applied at the point each value is computed
  (`FXClient.profile()`/`.prices()`, the `equicast_metrics.calculations`
  functions, `MetricsClient.metrics()`'s yfinance-sourced `cagr_1y`) rather
  than only at JSON/Parquet output time, so every consumer sees the same
  rounded value.
- `docs/aws-github-oidc-setup.md`: reference doc for how GitHub Actions
  authenticates to AWS — the OIDC federation `terraform.yml`, `deploy.yml`,
  and `fx-ingestion.yml` all use to assume a single IAM role — covering
  manual setup (the trust policy, a least-privilege permissions policy),
  verification, and common errors (trust policy mismatches, a duplicate
  OIDC provider in the account, missing `id-token` permissions).
- Infracost cost estimation: a new `infracost` job in `terraform.yml` posts
  (and updates) one PR comment with the estimated cost diff for both the
  `dev` and `prod` projects declared in the new `infracost.yml`, using new
  `infra/infracost-usage.yml` for rough S3/ECR usage estimates (storage,
  request volume) Infracost otherwise assumes are zero. It's a pure HCL
  diff — no `terraform plan`, state, or AWS credentials involved.
  `deploy.yml`'s `estimate-backend`/`estimate-frontend` jobs separately
  print a rough, size-based cost estimate (hardcoded, approximate AWS unit
  prices) for the image/bundle about to be pushed to the run's step summary,
  visible before either gate is approved.
- `infra/modules/ecr`: added an `aws_ecr_lifecycle_policy` capping
  `equicast-backend` at the 2 most recently pushed images.
- `equicast-stock` (`packages/stock/`): standalone package, mirroring
  `equicast-fx`'s design, for extracting stock ticker profiles
  (`StockClient(ticker).profile()`), returning ticker, name, quote type,
  exchange, currency, description, sector, industry, website, beta, payout
  ratio, dividend rate/yield, market cap, volume, day
  open/high/low/close/average, year open/high/low/close/average, 50-/200-day
  moving averages, address, country, region, full-time employees, CEO(s),
  IPO date, last updated, and source. The day/year/moving-average fields
  mirror `equicast-fx`'s `FXClient.profile()` exactly (same yfinance source
  fields, same midpoint/rounding logic, same trailing-52-week `year_*`
  window via a `history(period="1y")` call).
  `address` is formatted from `address1`/`address2`/`city`/`state`/`zip`,
  kept independent of the separate `country`/`region` fields (yfinance's own
  keys, not parsed out of the address string) so all three stay filterable.
  `ceos` is a list of `{"name", "role"}` entries, best-effort and tried in
  order: `companyOfficers` and `executiveTeam` (both structured — `role` is
  that person's actual title, e.g. "Chairman, President and CEO"), then a
  free-text pattern match against `longBusinessSummary` (`role` is always
  the literal string `"CEO"` there, since prose gives no real title) —
  yfinance has no dedicated CEO field. In the written Parquet file (not in
  `profile()`'s return value), `ceos` is JSON-encoded to a plain string
  column rather than a native list<struct> column — pandas/pyarrow
  round-trip the struct type fine, but common JS-based Parquet viewers just
  call `toString()` on nested objects and render `[object Object]` instead
  of the actual data; a JSON string reads correctly in any viewer.
  `ipo_date` is similarly best-effort, sourced from
  `firstTradeDateMilliseconds` (falling back to `firstTradeDateEpochUtc`) —
  yfinance has no true IPO date field either — formatted as a full ISO 8601
  datetime, same as `last_updated` (not just a date). Configured via
  `packages/stock/config/stocks.yaml` (AAPL, MSFT, GOOGL, AMZN, NVDA, META,
  TSLA, QCOM, AVGO by default); its CLI writes `stock=<TICKER>/profile.parquet`,
  reading tickers from that config or a `--tickers-json` string.
- `StockClient.prices()`: one daily OHLC record per trading day (ticker,
  currency, date, open/high/low/close/average, last updated,
  source=yfinance), mirroring `FXClient.prices()` — current year only by
  default (`ytd`), or the ticker's entire yfinance history with
  `full_load=True` (`max`). Unlike the from/to-currency pairs `equicast-fx`
  already knows, `currency` isn't available on `StockClient` itself, so
  `prices()` makes its own `get_info()` call to read it. The CLI writes one
  `price.parquet` per year covered to
  `stock=<TICKER>/year=<YYYY>/price.parquet`, alongside profile.parquet, via
  a new `--full-load` flag (same shape as `equicast-fx`'s).
- `equicast-stock-plan`: a second CLI entry point, identical in shape to
  `equicast-fx-plan`, splitting the configured tickers into chunks (capped
  at 256) for the ingestion workflow's matrix.
- `packages/stock/Dockerfile`, built and pushed to GHCR as a private image
  via the new `stock-image.yml` workflow.
- `packages/stock/scripts/smoke_test.py`, mirroring `equicast-fx`'s: a
  manual QA tool (not part of the automated `pytest` suite) exercising
  `StockClient.profile()`/`.prices()`, `DividendsClient.dividends()`,
  `MetricsClient.metrics()`/`.fundamentals()`, and the Parquet writers
  against live Yahoo Finance data, with `--tickers`, `--format json|parquet`,
  and `--full-load` options.
- `stock-ingestion.yml`: runs every 6 hours (and on demand) as two jobs,
  structured identically to `fx-ingestion.yml` — a `plan` job computing
  chunks via `equicast-stock-plan` and resolving the target
  environment/bucket, and an `ingest` matrix job uploading the resulting
  profile/price/dividend/metrics Parquet files to
  `s3://equicast-market-data-<env>/stock=<TICKER>/`, with a `full_load`
  input controlling prices'/dividends' history depth (same shape as
  `fx-ingestion.yml`'s). Shares the bucket and the
  `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` variables with
  `fx-ingestion.yml`. Scheduled at `0 2,8,14,20 * * *` — offset 2 hours from
  FX's `0 */6 * * *` — so the two pipelines never overlap even if a run
  takes longer than expected.
- `stock-ci.yml`: lint/type-check/test for `equicast-datafeed`,
  `equicast-metrics`, `equicast-dividends`, and `equicast-stock`, mirroring
  `fx-ci.yml`.
- `docs/stock-pipeline.md`, documenting the stock pipeline's architecture,
  local/Docker usage, and scheduled-run inputs (mirrors
  `docs/fx-pipeline.md`).
- `equicast_datafeed.DatafeedClient.get_balance_sheet()`/`.get_financials()`:
  fetch a ticker's annual balance sheet/income statement (`yf.Ticker(...).balance_sheet`/
  `.financials`), through the same rate-limit/retry wrapper as
  `get_info()`/`get_history()`.
- `MetricsClient.fundamentals()` (`equicast-metrics`): stock-only
  valuation/fundamental metrics — trailing/forward PE, trailing/forward EPS,
  PEG, price-to-book, price-to-sales, EV/EBITDA, gross/operating/profit
  margin, return on equity/assets, debt-to-equity, and free cash flow per
  share. For each field, prefers yfinance's `.info` directly, then a ratio
  built from other `.info` fields, and only as a last resort a line item
  pulled from the new `get_balance_sheet()`/`get_financials()` calls
  (fetched lazily, at most once each, since most tickers resolve every field
  from `.info` alone). PEG falls back to `trailing_pe / (earningsGrowth * 100)`
  when yfinance doesn't report `trailingPegRatio`/`pegRatio`. Raises the new
  `equicast_metrics.UnsupportedSymbolError` for an FX symbol (one ending in
  `"=X"`) — FX pairs have no earnings or balance sheet, so this is
  `equicast-stock`-only; `equicast-fx` never calls it.
- `equicast-stock`'s CLI now also computes metrics: a new `_metrics_task`
  calls both `MetricsClient.metrics()` and `.fundamentals()` and merges them
  into one `stock=<TICKER>/metrics.parquet` row (via a new
  `write_metrics_parquet`), reconciling the two independently-computed
  `last_updated`/`source` pairs into one of each. `equicast-metrics` is now
  a dependency of `equicast-stock` (`pyproject.toml`, `Dockerfile`,
  `stock-image.yml`'s path filters).
- `equicast_datafeed.DatafeedClient.get_dividends()`: fetches a symbol's
  historical dividends (`yf.Ticker(...).dividends`, ex-dividend date to cash
  amount per share) through the same rate-limit/retry wrapper as the other
  `get_*` methods.
- `equicast-dividends` (`packages/dividends/`): a new standalone package,
  generic across any yfinance equity-like symbol the same way
  `equicast-metrics`' `MetricsClient` is (not `equicast-stock`-specific, so
  a future ETF package can reuse it). `DividendsClient(symbol).dividends()`
  returns one record per ex-dividend date —
  `{ticker, currency, ex_dividend_date, price, last_updated, source}` —
  `price` being the dividend cash amount per share, not a stock price.
  Defaults to the current calendar year only (client-side filtering, since
  yfinance's dividends call has no period parameter of its own — the full
  series is always fetched in one call); `dividends(full_load=True)` returns
  every year instead. Deliberately has no `payment_date` field: yfinance's
  dividend history (scraped from Yahoo's dividend table) only ever has
  ex-dividend date and amount, for any ticker, at any point in history.
  Constructing a `DividendsClient` shows its own `EQUICAST_DIVIDENDS_DISCLAIMER`
  (distinct text from `equicast-datafeed`'s `YFINANCE_DATA_DISCLAIMER`, unlike
  `FXClient`/`StockClient` which reuse it) so it's always visible on its own,
  the same way `equicast-metrics`' disclaimer is, rather than silently
  deduped away when `DatafeedClient`'s disclaimer already fired earlier in
  the same process.
- Wired `equicast-dividends` into `equicast-stock`: a new `_dividends_task`
  in the CLI writes `stock=<TICKER>/year=<YYYY>/dividend.parquet` per year
  covered (via a new `write_dividend_parquet`), reusing the same
  `--full-load` flag as prices. `equicast-dividends` is now a dependency of
  `equicast-stock` (`pyproject.toml`, `Dockerfile`, `stock-image.yml`'s path
  filters) and of the root workspace (`pyproject.toml`), with its own
  `mypy`/`pytest` hooks added to `.pre-commit-config.yaml` and
  `docs/local-setup.md` gaining the stock packages' setup instructions it
  was previously missing.
- `equicast-etf` (`packages/etf/`): new standalone package, mirroring
  `equicast-stock`'s design (same starting point `equicast-stock` itself
  had). `ETFClient(ticker).profile()` returns ticker, name, quote type,
  exchange, currency, description, category, fund family, website, beta,
  expense ratio, dividend rate/yield, total assets, NAV price, volume,
  day/year price range and moving averages, YTD/3yr/5yr average returns,
  inception date, last updated, and source. Several `equicast-stock`
  profile fields don't apply to a fund and
  are dropped (`sector`/`industry`, `market_cap`, `payout_ratio`, `ceos`,
  `address`/`country`/`region`/`full_time_employees`) or re-sourced from a
  different yfinance field under the same name (`beta` here comes from
  yfinance's `beta3Year`, not a plain `beta` — yfinance has none for ETFs;
  `ipo_date` becomes `inception_date`, sourced from yfinance's
  `fundInceptionDate` instead of `firstTradeDateMilliseconds`/
  `firstTradeDateEpochUtc`, though those remain the fallback if
  `fundInceptionDate` is missing). `website` is the one field not sourced
  from yfinance at all — yfinance never populates it for ETFs (confirmed
  empty across Vanguard/iShares/Invesco/State Street/Schwab/BlackRock-issued
  funds) — so it's looked up from a small static `fund_family` →
  issuer-website map instead, matched by substring since `fundFamily` itself
  varies by ticker for the same issuer. Configured via
  `packages/etf/config/etfs.yaml` (VOO, QQQ, VTI, AGG, GLD by default —
  diversified across categories/issuers rather than picked for any other
  reason); its CLI writes `etf=<TICKER>/profile.parquet`, reading tickers
  from that config or a `--tickers-json` string.
- `ETFClient.prices()`: one daily OHLC record per trading day (ticker,
  currency, date, open/high/low/close/average, last updated,
  source=yfinance), mirroring `StockClient.prices()`/`FXClient.prices()` —
  current year only by default (`ytd`), or the ticker's entire yfinance
  history with `full_load=True` (`max`). `currency` isn't already known by
  `ETFClient`, so `prices()` makes its own `get_info()` call to read it. The
  CLI writes one `price.parquet` per year covered to
  `etf=<TICKER>/year=<YYYY>/price.parquet`, alongside profile.parquet, via a
  new `--full-load` flag (same shape as `equicast-stock`'s).
- Wired `equicast-dividends` into `equicast-etf`: a new `_dividends_task` in
  the CLI writes `etf=<TICKER>/year=<YYYY>/dividend.parquet` per year
  covered (via a new `write_dividend_parquet`), reusing the same
  `--full-load` flag as prices. `DividendsClient` is the same generic,
  symbol-keyed client `equicast-stock` already consumes — not duplicated
  for ETFs — so `equicast-etf` gets dividend history with no new
  dividend-fetching logic of its own. `equicast-dividends` is now a
  dependency of `equicast-etf` (`pyproject.toml`, `Dockerfile`,
  `etf-ci.yml`'s/`etf-image.yml`'s path filters).
- Wired `equicast-metrics` into `equicast-etf`: a new `_metrics_task` in the
  CLI writes `etf=<TICKER>/metrics.parquet` (via a new
  `write_metrics_parquet`, ticker-keyed the same way `equicast-stock`'s is).
  Only calls `MetricsClient.metrics()` (volatility, Sharpe ratio, max
  drawdown, CAGR 1/2/3/5/10y) — deliberately **not** `.fundamentals()`,
  unlike `equicast-stock`: checked live against VOO/QQQ/AGG/GLD first, and
  12-13 of its 15 valuation fields came back `None` for every one of them,
  with the couple that didn't (`trailing_pe`, `price_to_book`) being an
  inconsistent yfinance aggregate-portfolio figure rather than a genuine
  fund fundamental. The fund-level figures that matter for an ETF (expense
  ratio, NAV, AUM, category, YTD/3yr/5yr returns) already live in
  `profile()`, so there was no gap for a `fundamentals()`-style tier to
  fill. `equicast-metrics` is now a dependency of `equicast-etf`
  (`pyproject.toml`, `Dockerfile`, `etf-ci.yml`'s/`etf-image.yml`'s path
  filters).
- Wired `equicast-events` into `equicast-etf`: a new `_events_task` in the
  CLI writes `etf=<TICKER>/year=<YYYY>/events.parquet` per year covered
  (via a new `write_events_parquet`, using the same pinned pyarrow
  `_EVENTS_SCHEMA` as `equicast-stock`'s — kept as its own copy since
  `equicast_stock` isn't a dependency of `equicast_etf`), reusing the same
  `--full-load` flag as prices/dividends. `EventsClient` is the same
  generic, symbol-keyed client `equicast-stock` already consumes. Checked
  live for all 5 configured tickers first: `earnings`/`rating` event types
  are always empty for an ETF (no earnings reports or analyst coverage for
  a fund), so `events.parquet` in practice only ever has `"split"` rows —
  but those are real: VOO (2013), QQQ (2000, 2-for-1), and VTI (2008,
  2-for-1) each have exactly one in their full yfinance history; AGG and
  GLD have none. `equicast-events` is now a dependency of `equicast-etf`
  (`pyproject.toml`, `Dockerfile`, `etf-ci.yml`'s/`etf-image.yml`'s path
  filters).
- `equicast-etf-plan`: a second CLI entry point, identical in shape to
  `equicast-stock-plan`, splitting the configured tickers into chunks
  (capped at 256) for the ingestion workflow's matrix.
- `packages/etf/Dockerfile`, built and pushed to GHCR as a private image via
  the new `etf-image.yml` workflow.
- `packages/etf/scripts/smoke_test.py`, mirroring `equicast-stock`'s: a
  manual QA tool (not part of the automated `pytest` suite) exercising
  `ETFClient.profile()`/`.prices()`, `DividendsClient.dividends()`,
  `EventsClient.events()`, `MetricsClient.metrics()`, and the Parquet
  writers against live Yahoo Finance data, with `--tickers`,
  `--format json|parquet`, and `--full-load` options.
- `etf-ingestion.yml`: runs every 6 hours (and on demand) as two jobs,
  structured identically to `fx-ingestion.yml`/`stock-ingestion.yml` — a
  `plan` job computing chunks via `equicast-etf-plan` and resolving the
  target environment/bucket, and an `ingest` matrix job uploading the
  resulting profile/price/dividend/events/metrics Parquet files to
  `s3://equicast-market-data-<env>/etf=<TICKER>/`, with a `full_load` input
  controlling prices'/dividends'/events' history depth (same shape as
  `fx-ingestion.yml`'s/`stock-ingestion.yml`'s). Shares the bucket and the
  `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` variables with
  `fx-ingestion.yml`/`stock-ingestion.yml`. Scheduled at `0 4,10,16,22 * * *`
  — offset 4 hours from FX's `0 */6 * * *` and 2 hours from stock's
  `0 2,8,14,20 * * *` — so none of the three pipelines overlap even if a run
  takes longer than expected.
- `etf-ci.yml`: lint/type-check/test for `equicast-datafeed`,
  `equicast-metrics`, `equicast-dividends`, `equicast-events`, and
  `equicast-etf`, mirroring `stock-ci.yml`.
- `docs/etf-pipeline.md`, documenting the ETF pipeline's architecture,
  local/Docker usage, and scheduled-run inputs (mirrors
  `docs/stock-pipeline.md`).
- Added an ETF section to `infra/infracost-usage.yml`'s
  `module.market_data_bucket.aws_s3_bucket.this` estimate, sized from real
  per-file measurements (profile.parquet ~22-23KB, rounded to 25KB/ticker;
  price.parquet ~14KB for a partial year, scaling to ~20KB/year — the same
  figure the Stock section uses; dividend.parquet ~4KB for a partial year
  across VOO/QQQ/VTI/AGG — GLD pays none — scaling to ~5KB/year, smaller
  than the Stock section's assumed 10KB/year since ETF distributions here
  carry no other per-row fields; events.parquet ~7.2KB per file that
  actually exists — modeled as up to 1 accumulated file per ticker rather
  than one per year like price/dividend, since splits are rare (3 of 5
  configured tickers have exactly one split ever, not one per year);
  metrics.parquet ~6.7KB, identical across tickers since the schema is
  fixed, notably smaller than the Stock
  section's 20KB since it's risk/performance only, no fundamentals) rather
  than a placeholder, following the same real-sample approach the Stock
  section was re-sized to use.

### Changed

- Re-sized `infra/infracost-usage.yml`'s Stock section from real per-file
  estimates instead of placeholders: profile.parquet ~30KB and
  metrics.parquet ~20KB (one-time snapshots), plus price.parquet ~20KB/year,
  dividend.parquet ~10KB/year, and events.parquet ~10KB/year — the latter
  three now projected across 20 years of accumulated `year=<YYYY>`
  partitions per ticker (~850KB/ticker total) rather than only the current
  year, and now including `events.parquet` in both the size and PUT-request
  counts. `packages/stock/config/stocks.yaml`'s cost-estimate comment
  updated to match.
- Restructured the repo: `equicast`, `equicast-datafeed`, and `equicast-fx`
  now live under `packages/<name>/` (each its own independent distribution,
  own `pyproject.toml`, own `src/` layout). The root `pyproject.toml` became a
  virtual uv workspace root (`[tool.uv.workspace]` only, no `[project]` of its
  own) listing `packages/equicast`, `packages/datafeed`, `packages/fx`, and
  `backend` as members, sharing one lockfile/`.venv` for local dev and CI.
- Replaced the Terraform-managed, FX-scoped GitHub OIDC IAM role with a
  single, manually-created role used by all three AWS-touching workflows
  (`terraform.yml`, `deploy.yml`, `fx-ingestion.yml`), referenced by one
  repo secret, `AWS_ROLE_ARN`. Removes the circularity of Terraform needing
  AWS credentials to create the very OIDC setup meant to replace long-lived
  credentials — the provider and role are now bootstrapped once, manually,
  outside Terraform's management. `deploy.yml` and `terraform.yml` also
  moved off static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` secrets onto
  this same role. Removed `infra/modules/github_oidc_role/` and the
  `fx_ingestion_role_arn` Terraform output entirely; documented the manual
  setup in `docs/aws-github-oidc-setup.md`.
- Default AWS region changed from `us-east-1` to `eu-west-1` across
  Terraform (`aws_region` variable, `terraform.tfvars.example`, the
  commented remote-state backend example) and every workflow's
  `AWS_REGION` fallback.
- Consolidated the GitHub Actions IAM role from
  `equicast-github-actions-prod-role` to a single `equicast-github-actions`,
  shared by dev and prod (matching what `docs/aws-github-oidc-setup.md`
  already documented); the `AWS_ROLE_ARN` repo secret was updated to match.
- `infra/backend.tf`: enabled the S3 remote state backend
  (`equicast-tf-state`, using Terraform's native S3 state locking —
  `use_lockfile`, no DynamoDB table needed), previously left fully commented
  out — every `terraform apply` in CI had been silently using a throwaway
  local backend on the ephemeral runner, so Terraform had no memory of
  previously-created resources between runs. State is split per environment
  via `-backend-config="key=..."` at `terraform init` time
  (`equicast/dev/terraform.tfstate`, `equicast/prod/terraform.tfstate`),
  since a backend block's `key` can't be interpolated with
  `var.environment`. `infra/providers.tf`'s `required_version` bumped to
  `>= 1.10` for native locking support. Documented in new
  `docs/terraform-state-setup.md`, including the bucket bootstrap steps and
  the `terraform import` runbook for resources created by earlier `apply`
  runs before the backend existed.
- Dev/prod environment split, gated behind explicit approval: `terraform.yml`'s
  `apply` job is now `apply-dev` (runs automatically on push to `main`,
  `-var environment=dev`) followed by `apply-prod` (`-var environment=prod`,
  gated behind the `production` GitHub Environment's required reviewers).
  `deploy.yml` similarly splits backend/frontend each into an `estimate-*`
  job (builds the image/bundle once) plus `deploy-*-dev` (gated behind a new
  `deploy-dev` environment) and `deploy-*-prod` (gated behind `production`),
  promoting the exact artifact `estimate-*` built rather than rebuilding.
- Disabled S3 bucket versioning on `market_data_bucket` (cost reasons); it
  now uses the `s3_bucket` module's default (`false`), same as
  `frontend_bucket` already did.
- Fixed `deploy-backend-prod`'s image promotion: `equicast-backend` is
  `IMMUTABLE`, so re-pointing the `prod` tag on a second promotion would
  have failed (`ImageAlreadyExistsException`) — it now deletes the existing
  `prod` tag first (a no-op the first time).
- Paused deploying the frontend/backend, since there's nothing ready to
  ship yet and keeping the S3 bucket/ECR repo around just to sit empty
  costs money for nothing: `infra/main.tf`'s `frontend_bucket`/`backend_ecr`
  modules and their outputs in `infra/outputs.tf` are commented out (not
  deleted), and `deploy.yml`'s backend/frontend jobs are likewise commented
  out and replaced by a no-op `paused` job so the workflow stays valid and
  green. `market_data_bucket` and `fx-ingestion.yml` are unaffected.
- Fixed `fx-ingestion.yml` uploading to `s3:///fx=<PAIR>/...` (empty bucket
  name, `aws s3 cp` rejecting it with `Invalid bucket name ""`): the
  `MARKET_DATA_BUCKET` variable it read had never been set anywhere. Added
  a `workflow_dispatch` `environment` input (`dev`/`production`, default
  `dev`) and a `plan`-job step that resolves the target environment —
  the scheduled trigger always resolves to `production` (there's no input
  to read on a cron run), manual runs use the input — and looks up the
  matching bucket from two new plain repo variables,
  `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` (not scoped to the
  `dev`/`production` GitHub Environments, since `production`'s
  required-reviewer rule would otherwise pause every scheduled run pending
  approval). Fails fast with a clear `::error::` if the relevant variable
  is unset, rather than surfacing the confusing empty-bucket AWS error.
  Documented in `docs/fx-pipeline.md`.
- Sized `infra/infracost-usage.yml`'s `market_data_bucket` estimate from
  per-file Parquet sizes instead of a flat guess: `storage_gb` (`20` →
  `0.01`) and `monthly_tier_1_requests` (`5000` → `1500`) are now computed
  from profile.parquet (~15KB), metrics.parquet (~10KB), and price.parquet
  (~20KB/year) against the pair count in
  `packages/fx/config/fx_pairs.yaml` (currently 4) and `fx-ingestion.yml`'s
  6-hourly schedule — see that file's comments for the formula.
  `packages/fx/config/fx_pairs.yaml` now points back at it, so the cost
  estimate isn't forgotten the next time the pair list changes.
- Extended the same `market_data_bucket` estimate with a Stock section,
  broken out and summed alongside FX's: profile.parquet (~45KB/ticker
  placeholder) + price.parquet (~20KB/year) + the new metrics.parquet
  (~15KB/ticker placeholder) against `packages/stock/config/stocks.yaml`'s
  9 tickers and `stock-ingestion.yml`'s 6-hourly (offset) schedule —
  `monthly_tier_1_requests` (`3700` → `4800`) now covers both pipelines'
  three files/run each. `packages/stock/config/stocks.yaml` now points back
  at it too.
- Extended the Stock section again for the new dividend.parquet (~2KB/ticker
  placeholder — just a handful of rows per year, often none at all):
  `storage_gb` stays `0.01` (still well under 1GB) but
  `monthly_tier_1_requests` (`4800` → `5900`) now covers four files/run
  (profile + price + dividend + metrics) instead of three.
