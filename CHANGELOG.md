# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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

### Changed

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
