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
│   └── holdings/        # Django app: user-owned holdings CRUD, nested under an account/pie/watchlist (S3 JSON via equicast-core)
├── frontend/            # React (Vite) UI
├── infra/               # Terraform for AWS (S3 data lake, ECR, static site bucket)
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

`equicast-core` is a small generic package (boto3, no Django import) with six clients — `MarketDataClient` (pyarrow, reads the ingestion pipelines' S3 Parquet layout), `UserProfileClient` (DynamoDB user profiles), `AccountsClient` (S3 JSON, one object per user at `accounts/<user_id>.json`, optimistic concurrency via S3 conditional writes), `PiesClient` (S3 JSON, same shape, at `pies/<user_id>.json`, each pie nested under an `account_id`), `WatchlistsClient` (S3 JSON, same shape, at `watchlists/<user_id>.json`, user-level rather than nested under an account), and `HoldingsClient` (S3 JSON, same shape, at `holdings/<user_id>.json`, each holding nested under exactly one of `account_id`/`pie_id`/`watchlist_id`; pie holdings also carry `allocation_pct` and only ever change via an atomic add/remove/reallocate batch, since a pie's allocations must always sum to exactly 100%) — currently only consumed by the backend, but not backend-specific code itself:

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

Needs `USER_DATA_BUCKET` set (no default), plus the same Auth0 settings above, to use `/api/accounts/...`/`/api/pies/...`/`/api/watchlists/...`/`/api/holdings/...` — e.g. `USER_DATA_BUCKET=equicast-user-data-dev`.

`MAX_ACCOUNTS`/`MAX_PIES`/`MAX_WATCHLISTS` (defaults `5`/`20`/`5`, matching `equicast_core`'s own client defaults) tune the accounts-per-user, pies-per-account, and watchlists-per-user caps without a code change — see `infra/variables.tf`'s `max_accounts`/`max_pies`/`max_watchlists`, set per-environment via the `development`/`production` GitHub Environments' `MAX_ACCOUNTS`/`MAX_PIES`/`MAX_WATCHLISTS` variables. `MAX_HOLDINGS_FOR_ACCOUNT`/`MAX_HOLDINGS_FOR_PIE`/`MAX_HOLDINGS_FOR_WATCHLIST` (defaults `100`/`50`/`20`) tune the holdings-per-account/pie/watchlist caps the same way — see `infra/variables.tf`'s `max_holdings_for_account`/`max_holdings_for_pie`/`max_holdings_for_watchlist`.

API available at:
- `GET /health/` — no dependencies, used to validate the Lambda packaging (see `docs/` for the zip-packaging script)
- `GET /api/market/<asset_class>/<symbol>/profile/` — `asset_class` is one of `fx`/`stock`/`etf`
- `GET /api/market/<asset_class>/<symbol>/prices/` — current calendar year only
- `GET /api/identity/me/` — requires a valid Auth0-issued Bearer token; returns/creates the caller's profile (`user_id`, `default_currency`, defaulting to `"GBP"` on first login)
- `GET /api/accounts/` — requires a valid Auth0-issued Bearer token; lists the caller's accounts, each with its nested `pies` (with their own nested `holdings`) and its own direct `holdings`
- `POST /api/accounts/` — creates an account (`name`, `description`, `account_type`, `currency`); `409` once the caller has `MAX_ACCOUNTS`
- `GET /api/accounts/<id>/` — an account's details plus the same nested `pies`/`holdings` shape as the list endpoint
- `PATCH /api/accounts/<id>/` — partially updates an account
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
- `POST /api/holdings/` — creates a holding directly under `account_id` or `watchlist_id` (`ticker`, `asset_class`, and exactly one of the two — pie-scoped holdings go through the pie's batch endpoint instead); `409` for a duplicate ticker in that parent or once it's at its cap
- `GET /api/holdings/<id>/` — a holding's details
- `DELETE /api/holdings/<id>/` — deletes an account-direct or watchlist holding (`400` for a pie-scoped one); no `PATCH`

```bash
uv run pytest
uv run mypy . --ignore-missing-imports
```

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

Phase 0 (design tokens + app shell) is in place: `src/styles/tokens.css` ports
[Resource Planner](https://github.com/coldsofttech/resource-planner)'s OKLCH
design tokens as `--ec-*` custom properties (Palette A from
`docs/design/palette-options.html` — reused as-is), switched via
`data-theme` on `<html>` (set synchronously by an inline script in
`index.html`, before first paint, to avoid a flash of the wrong theme —
`ThemeToggle` flips it after that and persists the choice to
`localStorage`). `src/components/shell/` (`Topbar`, `MenuBar`, `AppShell`)
is the topbar + mega-menu shell, and `src/components/brand/` is the
`equiCast` wordmark + the finalized Candlestick Spear icon (see
`docs/design/README.md`) as a CSS-driven logo — no image request, reads
the same tokens so it flips with the theme too. Routing, the API client,
Auth0, and real domain pages are later phases, not built yet.

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
