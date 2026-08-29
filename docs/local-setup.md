# Local setup

How to get every part of the equiCast monorepo running on your machine.

## Repo layout

```
equiCast/
├── pyproject.toml       # virtual uv workspace root (no [project] of its own)
├── packages/
│   ├── equicast/        # Core Python package (yfinance ingestion, Parquet storage)
│   ├── datafeed/        # equicast-datafeed: resilient yfinance client (retries, rate limits)
│   ├── metrics/         # equicast-metrics: volatility, Sharpe ratio, max drawdown, CAGR
│   └── fx/              # equicast-fx: FX pair data extraction, containerized, pushed to GHCR
├── backend/             # Django REST API (uv workspace member, depends on equicast)
│   └── market_data/     # Django app exposing market data endpoints
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
- Docker, if you want to build/run the `equicast-fx` image locally
- Terraform >= 1.7 and AWS credentials, only if you're touching `infra/`

## One-time workspace setup

```bash
uv sync --all-packages --extra dev   # creates .venv, installs every workspace package
```

Every Python package below shares that one `.venv`/lockfile — you don't
re-run `uv sync` per package, just `cd` into it and `uv run ...`.

## Core package (`equicast`)

```bash
cd packages/equicast
uv run pytest
uv run mypy src/
```

## Backend (Django REST)

```bash
cd backend
uv run manage.py migrate
uv run manage.py runserver
```

API available at `http://localhost:8000/api/market-data/<ticker>/`.

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

## Infrastructure (Terraform)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
```

Reviews (doesn't apply) the S3 buckets and ECR repo described in
[fx-pipeline.md](fx-pipeline.md#deploying-the-infrastructure). The IAM role
Terraform itself authenticates through is created manually, not by
Terraform — see [aws-github-oidc-setup.md](aws-github-oidc-setup.md).

## Pre-commit hooks

```bash
uvx pre-commit install
uvx pre-commit run --all-files
```

Runs ruff, mypy, and pytest (unit) for the core package, Django backend, and
the datafeed/metrics/fx packages, plus eslint and vitest (unit) for the React
frontend. See `.pre-commit-config.yaml`.

## CI/CD workflows

- `backend-ci.yml` — ruff, mypy, and pytest for the core package and Django backend via `uv`
- `fx-ci.yml` — ruff, mypy, and pytest for `equicast-datafeed`, `equicast-metrics`, and `equicast-fx`
- `frontend-ci.yml` — eslint, vitest, and build for the React app
- `terraform.yml` — `fmt`/`validate`/`plan` on PRs, `apply` on merge to `main`
- `deploy.yml` — builds/pushes the backend image to ECR and syncs the frontend build to S3
- `fx-image.yml` / `fx-ingestion.yml` — build the FX pipeline's image and run it on a
  schedule; see [fx-pipeline.md](fx-pipeline.md) for details
