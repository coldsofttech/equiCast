# equiCast

Equity market data ingestion, storage, and forecasting toolkit.

## Structure

```
equiCast/
├── pyproject.toml       # virtual uv workspace root (no [project] of its own)
├── packages/
│   ├── equicast/        # Core Python package (yfinance ingestion, Parquet storage)
│   ├── datafeed/        # equicast-datafeed: resilient yfinance client (retries, rate limits)
│   └── fx/              # equicast-fx: FX pair profiles, containerized, pushed to GHCR
├── backend/             # Django REST API (uv workspace member, depends on equicast)
│   └── market_data/     # Django app exposing market data endpoints
├── frontend/            # React (Vite) UI
├── infra/               # Terraform for AWS (S3 data lake, ECR, static site bucket, OIDC role)
├── data/                # Local Parquet cache (gitignored)
└── .github/workflows/   # CI/CD pipelines
```

Every package under `packages/` (and `backend/`) is an independently
installable/publishable distribution with its own `pyproject.toml` — the root
`pyproject.toml` only declares the `uv` workspace (shared lockfile, one
`.venv`) and repo-wide `ruff`/`mypy` config; it installs nothing itself.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python dependency and virtualenv management
- Node.js 22+ for the frontend
- Terraform >= 1.7 and AWS credentials for infrastructure changes

## Core package (`equicast`)

```bash
uv sync --all-packages --extra dev   # creates .venv, installs every workspace package
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

## FX data (`equicast-datafeed`, `equicast-fx`)

`equicast-datafeed` is a standalone package providing a resilient yfinance
client (rate limiting + retry-with-backoff). `equicast-fx` is a standalone,
class-based package built on it that extracts FX pair profiles:

```bash
cd packages/datafeed && uv run pytest && uv run mypy src/
cd ../fx && uv run pytest && uv run mypy src/
```

```python
from equicast_fx import FXClient

FXClient("GBP", "USD").profile()
# {"from_currency": "GBP", "to_currency": "USD", "exchange": "CCY",
#  "region": "US", "description": "GBP/USD",
#  "last_updated": "2026-08-28T21:29:05+00:00", "source": "yfinance",
#  "day_open": 1.3594, "day_high": 1.3598, "day_low": 1.3527,
#  "day_close": 1.3537, "day_average": 1.3563,
#  "year_open": 1.3505, "year_high": 1.3847, "year_low": 1.3012,
#  "year_close": 1.3537, "year_average": 1.3429,
#  "moving_average_50_days": 1.3417, "moving_average_200_days": 1.3431}
```

`day_*`/`moving_average_*` come straight from yfinance's `.info` (`day_close`
is the live price — FX has no settled daily close). `year_*` uses yfinance's
own trailing-52-week window (`fiftyTwoWeekHigh`/`Low`); `year_open` is the
first `Open` from a `history(period="1y")` call (the only field with no
direct equivalent), `year_close` mirrors `day_close`, and both `*_average`
fields are the high/low midpoint, not a mean of daily closes.

The FX pairs to extract are configured in `packages/fx/config/fx_pairs.yaml`
(defaults: GBP→USD, USD→GBP, GBP→EUR, EUR→GBP). The CLI writes one Parquet
file per pair, and can read pairs from a YAML config or a JSON string:

```bash
cd packages/fx
uv run equicast-fx --config config/fx_pairs.yaml --out ./output
uv run equicast-fx --pairs-json '[{"from":"GBP","to":"USD"}]' --out ./output
# -> ./output/fx=GBPUSD/profile.parquet, fx=USDGBP/profile.parquet, ...
```

`--max-workers`/`--max-calls`/`--period-seconds` control concurrency and the
shared rate limit (defaults: 1/1/1.0 — sequential and conservative); the
ingestion workflow below overrides them for throughput.

`packages/fx/Dockerfile` containerizes the CLI; `fx-image.yml` builds and
pushes it to GHCR as a private image (`ghcr.io/<owner>/equicast-fx`) — the
config file isn't baked in as the only input, since pairs can also be passed
via `--pairs-json` at runtime. `fx-ingestion.yml` runs every 6 hours (and on
demand) with two jobs:

1. **plan** — runs `equicast-fx-plan` to split the configured pairs into
   chunks (default target: 300 pairs/chunk), capped at 256 chunks — the
   maximum jobs GitHub allows in one workflow matrix. If the pair list would
   need more than 256 chunks at the target size, the chunk size grows instead
   of dropping pairs.
2. **ingest** — a matrix job (default `max-parallel: 20`, tunable) with one
   leg per chunk: pulls the image, passes its chunk via `--pairs-json`, and
   uploads the resulting Parquet files to
   `s3://equicast-market-data-<env>/fx=<PAIR>/profile.parquet`. Each leg runs
   on its own GitHub-hosted runner (a separate source IP hitting Yahoo
   Finance), and each container also fetches its chunk's pairs concurrently
   — so throughput scales both across and within legs. With today's 4 pairs
   this collapses to a single chunk/leg; at thousands of pairs it fans out
   automatically.

## Infrastructure (Terraform)

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
```

Provisions the `equicast-market-data-<env>` S3 bucket (shared by the backend's
on-demand cache and the FX ingestion pipeline), the frontend static site
bucket, the backend ECR repo, and a GitHub Actions OIDC IAM role scoped to
`s3://equicast-market-data-<env>/fx=*/*` for the FX ingestion workflow. Put its
`fx_ingestion_role_arn` output into the `AWS_FX_INGESTION_ROLE_ARN` repo
secret, and set the `MARKET_DATA_BUCKET` repo variable to the bucket name.

## Pre-commit hooks

```bash
uvx pre-commit install
uvx pre-commit run --all-files
```

Runs ruff, mypy, and pytest (unit) for the core package, Django backend, and
the datafeed/fx packages, plus eslint and vitest (unit) for the React
frontend. See `.pre-commit-config.yaml`.

## CI/CD

- `backend-ci.yml` — ruff, mypy, and pytest for the core package and Django backend via `uv`
- `fx-ci.yml` — ruff, mypy, and pytest for `equicast-datafeed` and `equicast-fx`
- `frontend-ci.yml` — eslint, vitest, and build for the React app
- `terraform.yml` — `fmt`/`validate`/`plan` on PRs, `apply` on merge to `main`
- `deploy.yml` — builds/pushes the backend image to ECR and syncs the frontend build to S3
- `fx-image.yml` — builds/pushes the `equicast-fx` image to GHCR (private) on changes to `packages/datafeed/`/`packages/fx/`
- `fx-ingestion.yml` — every 6 hours (and on demand): runs the image, uploads FX Parquet files to S3

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
