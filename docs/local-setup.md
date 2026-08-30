# Local setup

How to get every part of the equiCast monorepo running on your machine.

## Repo layout

```
equiCast/
├── pyproject.toml       # virtual uv workspace root (no [project] of its own)
├── packages/
│   ├── core/            # equicast-core: generic S3 Parquet reader (boto3+pyarrow), consumed by the backend
│   ├── datafeed/        # equicast-datafeed: resilient yfinance client (retries, rate limits)
│   ├── metrics/         # equicast-metrics: volatility, Sharpe ratio, max drawdown, CAGR + stock fundamentals
│   ├── dividends/       # equicast-dividends: generic dividend history for any equity-like symbol
│   ├── events/          # equicast-events: generic earnings/ratings/splits for any equity-like symbol
│   ├── fx/              # equicast-fx: FX pair data extraction, containerized, pushed to GHCR
│   └── stock/           # equicast-stock: stock ticker data extraction, containerized, pushed to GHCR
├── backend/             # Django REST API (uv workspace member, depends on equicast-core); zip-packaged for Lambda
│   └── market_data/     # Django app exposing real market data (reads S3 via equicast-core)
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
- Docker, if you want to build/run the `equicast-fx`/`equicast-stock` images locally
- Terraform >= 1.7 and AWS credentials, only if you're touching `infra/`

## One-time workspace setup

```bash
uv sync --all-packages --extra dev   # creates .venv, installs every workspace package
```

Every Python package below shares that one `.venv`/lockfile — you don't
re-run `uv sync` per package, just `cd` into it and `uv run ...`.

## Backend (Django REST) and `equicast-core`

`equicast-core` is a small generic package (boto3 + pyarrow, no Django import) that reads the ingestion pipelines' S3 Parquet layout — currently only consumed by the backend, but not backend-specific code itself:

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

API available at:
- `GET /health/` — no dependencies, used to validate the Lambda packaging (see `docs/` for the zip-packaging script)
- `GET /api/market/<asset_class>/<symbol>/profile/` — `asset_class` is one of `fx`/`stock`/`etf`
- `GET /api/market/<asset_class>/<symbol>/prices/` — current calendar year only

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
equity-like symbol), built the same way as `equicast-metrics` — currently
only `equicast-stock` consumes either. See
[stock-pipeline.md](stock-pipeline.md) for how to run the CLI, smoke-test
against live data with `scripts/smoke_test.py`, build the Docker image, and
deploy/execute the scheduled ingestion pipeline.

## Infrastructure (Terraform)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
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
and the datafeed/metrics/dividends/events/fx/stock packages, plus eslint and
vitest (unit) for the React frontend. See `.pre-commit-config.yaml`.

## CI/CD workflows

- `backend-ci.yml` — ruff, mypy, and pytest for `equicast-core` and the Django backend via `uv`
- `fx-ci.yml` — ruff, mypy, and pytest for `equicast-datafeed`, `equicast-metrics`, and `equicast-fx`
- `stock-ci.yml` — ruff, mypy, and pytest for `equicast-datafeed`,
  `equicast-metrics`, `equicast-dividends`, `equicast-events`, and
  `equicast-stock`
- `frontend-ci.yml` — eslint, vitest, and build for the React app
- `terraform.yml` — `fmt`/`validate`/`plan` on PRs, plus an Infracost cost-diff
  PR comment; on merge to `main`, `apply-dev` runs automatically and
  `apply-prod` waits for approval on the `production` GitHub Environment
  (see [terraform-state-setup.md](terraform-state-setup.md))
- `deploy.yml` — builds the backend image/frontend bundle once, posts a rough
  cost estimate, then `dev` and `prod` deploys each wait for approval on their
  own GitHub Environment (`deploy-dev`, `production`) before pushing/syncing
- `fx-image.yml` / `fx-ingestion.yml` — build the FX pipeline's image and run it on a
  schedule; see [fx-pipeline.md](fx-pipeline.md) for details
- `stock-image.yml` / `stock-ingestion.yml` — build the stock pipeline's image and run it
  on a schedule; see [stock-pipeline.md](stock-pipeline.md) for details
