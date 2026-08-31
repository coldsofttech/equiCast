# Local setup

How to get every part of the equiCast monorepo running on your machine.

## Repo layout

```
equiCast/
├── pyproject.toml       # virtual uv workspace root (no [project] of its own)
├── packages/
│   ├── core/            # equicast-core: shared AWS clients (S3 Parquet reads, DynamoDB user profiles), consumed by the backend
│   ├── datafeed/        # equicast-datafeed: resilient yfinance client (retries, rate limits)
│   ├── metrics/         # equicast-metrics: volatility, Sharpe ratio, max drawdown, CAGR + stock fundamentals
│   ├── dividends/       # equicast-dividends: generic dividend history for any equity-like symbol
│   ├── events/          # equicast-events: generic earnings/ratings/splits for any equity-like symbol
│   ├── fx/              # equicast-fx: FX pair data extraction, containerized, pushed to GHCR
│   ├── stock/           # equicast-stock: stock ticker data extraction, containerized, pushed to GHCR
│   └── etf/             # equicast-etf: ETF ticker data extraction, containerized, pushed to GHCR
├── backend/             # Django REST API (uv workspace member, depends on equicast-core); zip-packaged for Lambda
│   ├── market_data/     # Django app exposing real market data (reads S3 via equicast-core)
│   ├── identity/        # Django app: Auth0 JWT verification, first-login DynamoDB profile upsert
│   ├── accounts/        # Django app: user-owned accounts CRUD (S3 JSON via equicast-core)
│   ├── pies/            # Django app: user-owned pies CRUD, nested under an account (S3 JSON via equicast-core)
│   ├── watchlists/      # Django app: user-owned watchlists CRUD, user-level (S3 JSON via equicast-core)
│   ├── holdings/        # Django app: user-owned holdings CRUD, nested under an account/pie/watchlist (S3 JSON via equicast-core)
│   └── transactions/    # Django app: user-owned transactions CRUD, nested under a holding (S3 JSON via equicast-core)
├── frontend/            # React (Vite) UI
├── infra/               # Terraform for AWS (S3 data lake, ECR, static site bucket)
├── scripts/             # Repo-wide dev tooling (e.g. local-dev.ps1 — LocalStack)
├── data/                # Local Parquet cache (gitignored)
├── docs/                # This directory
└── .github/workflows/   # CI/CD pipelines
```

Every package under `packages/` (and `backend/`) is an independently
installable/publishable distribution with its own `pyproject.toml` — the root
`pyproject.toml` only declares the `uv` workspace (shared lockfile, one
`.venv`) and repo-wide `ruff`/`mypy` config; it installs nothing itself.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python dependency and virtualenv management
- Node.js 22+ for the frontend
- Docker, if you want to build/run the `equicast-fx`/`equicast-stock`/`equicast-etf` images locally
- Terraform >= 1.7 and AWS credentials, only if you're touching `infra/`

## One-time workspace setup

```bash
uv sync --all-packages --extra dev   # creates .venv, installs every workspace package
```

Every Python package below shares that one `.venv`/lockfile — you don't
re-run `uv sync` per package, just `cd` into it and `uv run ...`.

## Backend (Django REST) and `equicast-core`

`equicast-core` is a small generic package (boto3, no Django import) with seven clients — `MarketDataClient` (pyarrow, reads the ingestion pipelines' S3 Parquet layout), `UserProfileClient` (DynamoDB user profiles), `AccountsClient` (S3 JSON, one object per user at `accounts/<user_id>.json`, optimistic concurrency via S3 conditional writes), `PiesClient` (S3 JSON, same shape, at `pies/<user_id>.json`, each pie nested under an `account_id`), `WatchlistsClient` (S3 JSON, same shape, at `watchlists/<user_id>.json`, user-level rather than nested under an account), `HoldingsClient` (S3 JSON, same shape, at `holdings/<user_id>.json`, each holding nested under exactly one of `account_id`/`pie_id`/`watchlist_id`; pie holdings also carry `allocation_pct` and only ever change via an atomic add/remove/reallocate batch, since a pie's allocations must always sum to exactly 100%), and `TransactionsClient` (S3 JSON, but one object *per holding* rather than per user, at `transactions/<user_id>/<holding_id>.json` — every real query here is already holding-scoped, so this avoids rewriting a whole-user blob on every write; shaped by the holding's account's `transaction_type` — `AVERAGE`, a single mutable snapshot, or `TRANSACTION`, an immutable `BUY`/`SELL` log) — currently only consumed by the backend, but not backend-specific code itself:

```bash
cd packages/core
uv run pytest
uv run mypy src/
```

```bash
cd backend
uv run manage.py migrate
uv run manage.py runserver
```

Needs `MARKET_DATA_BUCKET` set (no default) to actually serve data — e.g. `MARKET_DATA_BUCKET=equicast-market-data-dev`, plus working AWS read credentials locally. Without it, the server still starts (only `GET /health/` and the admin work).

Needs `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, and `USER_PROFILES_TABLE` set (no defaults) to use `/api/identity/...` — see [auth0-setup.md](auth0-setup.md) for where the Auth0 values come from. Without them, `/api/market/...` is unaffected, but any `Authorization: Bearer` header fails to authenticate and `/api/identity/me/` always returns `401`.

Needs `USER_DATA_BUCKET` set (no default), plus the same Auth0 settings above, to use `/api/accounts/...`/`/api/pies/...`/`/api/watchlists/...`/`/api/holdings/...`/`/api/transactions/...` — e.g. `USER_DATA_BUCKET=equicast-user-data-dev`.

`MAX_ACCOUNTS`/`MAX_PIES`/`MAX_WATCHLISTS` (defaults `5`/`20`/`5`, matching `equicast_core`'s own client defaults) tune the accounts-per-user, pies-per-account, and watchlists-per-user caps without a code change — see `infra/variables.tf`'s `max_accounts`/`max_pies`/`max_watchlists`, set per-environment via the `development`/`production` GitHub Environments' `MAX_ACCOUNTS`/`MAX_PIES`/`MAX_WATCHLISTS` variables. `MAX_HOLDINGS_FOR_ACCOUNT`/`MAX_HOLDINGS_FOR_PIE`/`MAX_HOLDINGS_FOR_WATCHLIST` (defaults `100`/`50`/`20`) tune the holdings-per-account/pie/watchlist caps the same way — see `infra/variables.tf`'s `max_holdings_for_account`/`max_holdings_for_pie`/`max_holdings_for_watchlist`. `MAX_TRANSACTIONS_FOR_HOLDING` (default `500`) tunes the transactions-per-holding cap the same way — see `infra/variables.tf`'s `max_transactions_for_holding`.

API available at:
- `GET /health/` — no dependencies, used to validate the Lambda packaging (see `docs/` for the zip-packaging script)
- `GET /api/market/<asset_class>/<symbol>/profile/` — `asset_class` is one of `fx`/`stock`/`etf`
- `GET /api/market/<asset_class>/<symbol>/prices/` — current calendar year only
- `GET /api/market/search/` — ticker/name search; `?q=` required (at least 1 character), case-insensitive substring match against every published catalog's `ticker`/`name` (see `equicast_core.catalog`) — results are only as fresh as the last ingestion run, not a live bucket scan. Optional `?asset_class=` narrows to one of `fx`/`stock`/`etf`. Paginated (`?page=`, default `1`; `?page_size=`, default `50`, capped at `200`), returning `{count, page, page_size, total_pages, results}`
- `GET /api/identity/me/` — requires a valid Auth0-issued Bearer token; returns/creates the caller's profile (`user_id`, `default_currency`, defaulting to `"GBP"` on first login)
- `GET /api/accounts/` — requires a valid Auth0-issued Bearer token; lists the caller's accounts, each with its nested `pies` (with their own nested `holdings`) and its own direct `holdings`
- `POST /api/accounts/` — creates an account (`name`, `description`, `account_type`, `currency`, `transaction_type` — `AVERAGE` or `TRANSACTION`); `409` once the caller has `MAX_ACCOUNTS`
- `GET /api/accounts/<id>/` — an account's details plus the same nested `pies`/`holdings` shape as the list endpoint
- `PATCH /api/accounts/<id>/` — partially updates an account; `transaction_type` is rejected with `409` once the account has any transactions recorded under it
- `DELETE /api/accounts/<id>/` — deletes an account; `409` if it still has
  pies and/or direct holdings — pass `?force=true` to delete those along with the account
- `GET /api/pies/` — lists the caller's pies; optional `?account_id=` filter
- `POST /api/pies/` — creates a pie under `account_id` (`name`, `description`, `account_id`); `400` if `account_id` isn't one of the caller's own accounts; `409` once that account has `MAX_PIES`
- `GET /api/pies/<id>/` — a pie's details plus its nested `holdings`
- `PATCH /api/pies/<id>/` — partially updates a pie's `name`/`description` (`account_id` is immutable)
- `DELETE /api/pies/<id>/` — deletes a pie; `409` if it still has holdings — pass `?force=true` to delete those along with the pie
- `PUT /api/pies/<id>/holdings/` — the only way to add/remove/reallocate a pie's holdings (`{"add": [...], "remove": [...], "reallocate": [...]}`), validated atomically so the resulting holdings always sum to exactly 100% — see `backend/README.md`
- `GET /api/watchlists/` — lists the caller's watchlists (user-level, not nested under an account)
- `POST /api/watchlists/` — creates a watchlist (`name`, `description`); `409` once the caller has `MAX_WATCHLISTS`
- `GET /api/watchlists/<id>/` — a watchlist's details plus its nested `holdings`
- `PATCH /api/watchlists/<id>/` — partially updates a watchlist's `name`/`description`
- `DELETE /api/watchlists/<id>/` — deletes a watchlist; `409` if it still has holdings — pass `?force=true` to delete those along with the watchlist
- `GET /api/holdings/` — lists the caller's holdings; at most one of `?account_id=`/`?pie_id=`/`?watchlist_id=` may be given
- `POST /api/holdings/` — creates a holding directly under `account_id` or `watchlist_id` (`ticker`, `asset_class`, and exactly one of the two — pie-scoped holdings go through the pie's batch endpoint instead); `409` for a duplicate ticker in that parent or once it's at its cap. An optional nested `transaction` field records the holding's first transaction in the same request (not supported for watchlist holdings) — shaped by the owning account's `transaction_type`, see below
- `GET /api/holdings/<id>/` — a holding's details
- `DELETE /api/holdings/<id>/` — deletes an account-direct or watchlist holding (`400` for a pie-scoped one); no `PATCH`; cascades into deleting the holding's transactions
- `GET /api/transactions/` — lists the caller's transactions; optional `?holding_id=`, `?year=`, `?date_from=`/`?date_to=` filters (the date filters only ever match `TRANSACTION`-mode records — an `AVERAGE` record has no date). Omitting `?holding_id=` reads every holding's file, since transactions are stored one JSON object per holding — see `packages/core/README.md`
- `POST /api/transactions/` — records a transaction against an existing `holding_id` (`400` if the holding is fx or watchlist-scoped). `AVERAGE`-mode accounts require `no_of_shares`/`average_price` (`409` for a second record against the same holding — `PATCH` it instead); `TRANSACTION`-mode accounts require `no_of_shares`/`price`/`date`/`type` (`BUY` or `SELL`; `409` if a `SELL` exceeds the holding's net recorded shares, or once the holding is at `MAX_TRANSACTIONS_FOR_HOLDING`)
- `GET /api/transactions/<holding_id>/<id>/` — a transaction's details (nested under its holding, not a flat id — an id-only lookup would otherwise have to scan every holding's file)
- `PATCH /api/transactions/<holding_id>/<id>/` — updates an `AVERAGE`-mode record's `no_of_shares`/`average_price`; `400` for a `TRANSACTION`-mode record (immutable)
- `DELETE /api/transactions/<holding_id>/<id>/` — deletes a transaction

```bash
uv run pytest
uv run mypy . --ignore-missing-imports
```

## Backend against LocalStack (optional — no real AWS account needed)

`scripts/local-dev.ps1` (Windows PowerShell) starts [LocalStack](https://www.localstack.io/)
(S3 + DynamoDB), provisions the
`MARKET_DATA_BUCKET`/`USER_DATA_BUCKET`/`USER_PROFILES_TABLE` the backend needs,
and runs `manage.py runserver` against them — an end-to-end local loop
(accounts, pies, watchlists, holdings, transactions, and market data) with no
real AWS credentials or bucket required, and no LocalStack account/signup either.
Pinned to `localstack/localstack:4.14.0`, deliberately not `:latest` — starting
with the 2026.03.0 calendar-versioned release, even LocalStack's free tier
requires a `LOCALSTACK_AUTH_TOKEN` (a free account) just to start the image;
`4.14.0` is the last semver release before that requirement, so this stays
genuinely account-free at the cost of no further LocalStack updates beyond it.
It works with no code changes: every
`equicast-core` client just calls plain `boto3.client(...)`/`boto3.resource(...)`,
and boto3 (pinned `>=1.35.9`) already honors the `AWS_ENDPOINT_URL_S3`/
`AWS_ENDPOINT_URL_DYNAMODB` env vars the script sets to route those calls at
LocalStack instead of real AWS.

```powershell
.\scripts\local-dev.ps1                        # start LocalStack + the backend
.\scripts\local-dev.ps1 -SeedMarketData        # also ingest fx/stock/etf (per their packages/*/config/*.yaml) so /api/market/... has data
.\scripts\local-dev.ps1 -SeedMarketData -FullLoad  # same, but full price history instead of just the current year (slower, more network calls)
.\scripts\local-dev.ps1 -Stop                  # stop and remove the LocalStack container
.\scripts\local-dev.ps1 -Reset                 # wipe the LocalStack container/data and start fresh
```

`-SeedMarketData` runs the real `equicast-fx`/`equicast-stock`/`equicast-etf` CLIs
against live Yahoo Finance data (see [fx-pipeline.md](fx-pipeline.md)/
[stock-pipeline.md](stock-pipeline.md)/[etf-pipeline.md](etf-pipeline.md)) — the
LocalStack part is fully local, but this specific step makes real network calls.
Ctrl+C stops the backend and tears down the LocalStack container (nothing persists
across sessions — pass `-SeedMarketData` again next time you want data in it).

Two things it deliberately does **not** simulate:

- **Auth0** — `Auth0JWTAuthentication` always talks to a real Auth0 tenant (JWKS
  verification isn't something LocalStack can stand in for). Every `/api/...`
  view sets `permission_classes = [IsAuthenticated]` — including
  `/api/market/...` (`ProfileView`/`PricesView`/`SearchView`), not just
  `/api/accounts/...`/etc — so a request with no Bearer token `401`s
  regardless of whether `AUTH0_DOMAIN`/`AUTH0_AUDIENCE` are set server-side.
  Only `/health/` and the Django admin work with no token at all. Pass
  `-Auth0Domain`/`-Auth0Audience` (or export `$env:AUTH0_DOMAIN`/
  `$env:AUTH0_AUDIENCE` first) so the server can *verify* a token — see
  [auth0-setup.md](auth0-setup.md) for how to register a tenant/app — but you
  still need a genuine Auth0-issued token in hand (e.g. via the frontend's
  real login flow) to call anything under `/api/...` at all, LocalStack or not.
- **Lambda + API Gateway** — prod/dev deploy the backend as a Lambda behind
  API Gateway (`infra/main.tf`'s `backend_lambda`/`backend_api_gateway`
  modules), but the script runs the identical Django app via
  `manage.py runserver` instead, so edits reload instantly rather than needing
  a zip rebuild/redeploy per change. Only relevant if you're specifically
  debugging the packaging/handler/gateway-integration layer itself, which
  this script isn't meant to cover.

This only starts LocalStack + the backend — run `cd frontend && npm run dev`
in another terminal and open `http://localhost:5173` to drive it from the
browser (proxying `/api` to the backend, same as normal). Note that the
frontend's Auth0 login screen and the accounts/pies pages currently live on
`feat/frontend-routing-auth`, not `main` yet — check that branch out if
you're testing that flow end to end.

## Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

UI available at `http://localhost:5173`, proxying `/api` to the Django backend.

```bash
npm run lint
npm run test -- --run
```

## FX packages (`equicast-datafeed`, `equicast-metrics`, `equicast-fx`)

```bash
cd packages/datafeed && uv run pytest && uv run mypy src/
cd ../metrics && uv run pytest && uv run mypy src/
cd ../fx && uv run pytest && uv run mypy src/
```

See [fx-pipeline.md](fx-pipeline.md) for how to run the CLI, smoke-test
against live data with `scripts/smoke_test.py`, build the Docker image, and
deploy/execute the scheduled ingestion pipeline.

## Stock packages (`equicast-datafeed`, `equicast-metrics`, `equicast-dividends`, `equicast-events`, `equicast-stock`)

```bash
cd packages/datafeed && uv run pytest && uv run mypy src/
cd ../metrics && uv run pytest && uv run mypy src/
cd ../dividends && uv run pytest && uv run mypy src/
cd ../events && uv run pytest && uv run mypy src/
cd ../stock && uv run pytest && uv run mypy src/
```

`equicast-dividends`/`equicast-events` are generic (any yfinance
equity-like symbol), built the same way as `equicast-metrics` —
`equicast-stock` and `equicast-etf` both consume both. See
[stock-pipeline.md](stock-pipeline.md) for how to run the CLI, smoke-test
against live data with `scripts/smoke_test.py`, build the Docker image, and
deploy/execute the scheduled ingestion pipeline.

## ETF packages (`equicast-datafeed`, `equicast-metrics`, `equicast-dividends`, `equicast-events`, `equicast-etf`)

```bash
cd packages/datafeed && uv run pytest && uv run mypy src/
cd ../metrics && uv run pytest && uv run mypy src/
cd ../dividends && uv run pytest && uv run mypy src/
cd ../events && uv run pytest && uv run mypy src/
cd ../etf && uv run pytest && uv run mypy src/
```

`equicast-etf` implements `profile()`, `prices()`, dividends (via the same
generic `equicast-dividends`' `DividendsClient` that `equicast-stock`
uses), events (via the same generic `equicast-events`' `EventsClient` —
in practice only ever produces `"split"` rows for an ETF, since yfinance
has no earnings/analyst coverage for a fund), and risk metrics (via
`equicast-metrics`' `MetricsClient.metrics()`, not `.fundamentals()` —
stock-only, since valuation ratios don't apply to a fund the way they do a
company). See
[etf-pipeline.md](etf-pipeline.md) for how to run the CLI, smoke-test
against live data with `scripts/smoke_test.py`, build the Docker image, and
deploy/execute the scheduled ingestion pipeline.

## Infrastructure (Terraform)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # fill in auth0_domain/auth0_audience — see auth0-setup.md
terraform init -backend-config="key=equicast/dev/terraform.tfstate"
terraform plan -var environment=dev
```

Reviews (doesn't apply) the S3 buckets and ECR repo described in
[fx-pipeline.md](fx-pipeline.md#deploying-the-infrastructure). The IAM role
Terraform itself authenticates through is created manually, not by
Terraform — see [aws-github-oidc-setup.md](aws-github-oidc-setup.md). The
state bucket is likewise created manually — see
[terraform-state-setup.md](terraform-state-setup.md).

## Pre-commit hooks

```bash
uvx pre-commit install
uvx pre-commit run --all-files
```

Runs ruff, mypy, and pytest (unit) for `equicast-core`, the Django backend,
and the datafeed/metrics/dividends/events/fx/stock/etf packages, plus eslint and
vitest (unit) for the React frontend. See `.pre-commit-config.yaml`.

## CI/CD workflows

- `backend-ci.yml` — ruff, mypy, and pytest for `equicast-core` and the Django backend via `uv`
- `fx-ci.yml` — ruff, mypy, and pytest for `equicast-datafeed`, `equicast-metrics`, and `equicast-fx`
- `stock-ci.yml` — ruff, mypy, and pytest for `equicast-datafeed`,
  `equicast-metrics`, `equicast-dividends`, `equicast-events`, and
  `equicast-stock`
- `etf-ci.yml` — ruff, mypy, and pytest for `equicast-datafeed`,
  `equicast-metrics`, `equicast-dividends`, `equicast-events`, and
  `equicast-etf`
- `frontend-ci.yml` — eslint, vitest, and build for the React app
- `terraform.yml` — `fmt`/`validate`/`plan` on PRs, plus an Infracost cost-diff
  PR comment; on merge to `main`, `apply-dev` and `apply-prod` each wait for
  approval on their own GitHub Environment (`development`, `production`)
  (see [terraform-state-setup.md](terraform-state-setup.md))
- `deploy.yml` — builds the backend image/frontend bundle once, posts a rough
  cost estimate, then `dev` and `prod` deploys each wait for approval on their
  own GitHub Environment (`development`, `production`) before pushing/syncing
- `fx-image.yml` / `fx-ingestion.yml` — build the FX pipeline's image and run it on a
  schedule; see [fx-pipeline.md](fx-pipeline.md) for details
- `stock-image.yml` / `stock-ingestion.yml` — build the stock pipeline's image and run it
  on a schedule; see [stock-pipeline.md](stock-pipeline.md) for details
- `etf-image.yml` / `etf-ingestion.yml` — build the ETF pipeline's image and run it
  on a schedule; see [etf-pipeline.md](etf-pipeline.md) for details
