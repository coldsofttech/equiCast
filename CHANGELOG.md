# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `equicast-datafeed` (`packages/datafeed/`): standalone package providing a
  resilient yfinance client with rate limiting and retry-with-backoff,
  reusable by any future market-data package.
- `equicast-fx` (`packages/fx/`): standalone, class-based package for
  extracting FX pair profiles (`FXClient(from_currency, to_currency).profile()`),
  returning from/to currency, exchange, region, description, last updated, and
  source. Configured via `packages/fx/config/fx_pairs.yaml` (GBP/USD, USD/GBP,
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
- `fx-ci.yml`: ruff, mypy, and pytest for `equicast-datafeed` and `equicast-fx`.
- Terraform `github_oidc_role` module: provisions a GitHub Actions OIDC
  provider and IAM role scoped to `s3://equicast-market-data-<env>/fx=*/*`,
  used by `fx-ingestion.yml` instead of long-lived AWS credentials.

### Changed

- Restructured the repo: `equicast`, `equicast-datafeed`, and `equicast-fx`
  now live under `packages/<name>/` (each its own independent distribution,
  own `pyproject.toml`, own `src/` layout). The root `pyproject.toml` became a
  virtual uv workspace root (`[tool.uv.workspace]` only, no `[project]` of its
  own) listing `packages/equicast`, `packages/datafeed`, `packages/fx`, and
  `backend` as members, sharing one lockfile/`.venv` for local dev and CI.

## [0.1.0] - 2026-08-29

### Added

- Initial project scaffold with `equicast`, a core Python package (yfinance ingestion,
  Parquet storage) as the root of a uv workspace.
- Django REST backend (`backend/`) exposing market data at `/api/market-data/<ticker>/`,
  depending on `equicast` via the uv workspace.
- React (Vite) frontend (`frontend/`) with a minimal UI for fetching ticker history.
- Terraform configuration (`infra/`) for AWS: S3 market-data bucket, S3 static-site
  bucket for the frontend, and an ECR repository for the backend image.
- GitHub Actions workflows: backend CI (ruff, mypy, pytest), frontend CI (eslint,
  vitest, build), Terraform plan/apply, and deploy (ECR push + S3 sync).
- Pre-commit hooks (`.pre-commit-config.yaml`) covering ruff, mypy, and pytest
  (unit) for the core package and Django backend, plus eslint and vitest (unit)
  for the React frontend.
