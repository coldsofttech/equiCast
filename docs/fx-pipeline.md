# FX pipeline: deployment and execution

How the `equicast-fx` scheduled ingestion pipeline is built, deployed, and
run. For local package setup (installing deps, running unit tests), see
[local-setup.md](local-setup.md). For what the `profile`/`price`/`metrics`
data actually contains, see the root [README](../README.md).

## Architecture

```
packages/fx/config/fx_pairs.yaml   (the pairs to extract)
        │
        ▼
equicast-fx CLI  ── uses ──▶  equicast-datafeed (rate limiting + retries)
        │              └────▶  equicast-metrics (volatility, Sharpe, drawdown, CAGR)
        │                              │
        │                              ▼
        │                       Yahoo Finance (yfinance)
        ▼
Parquet files (profile.parquet, price.parquet, metrics.parquet)
        │
        ▼
GitHub Actions (fx-ingestion.yml)  ──▶  S3 (s3://equicast-market-data-<env>/)
```

`packages/fx/Dockerfile` containerizes the CLI. `fx-image.yml` builds and
pushes it to GHCR as a **private** image (`ghcr.io/<owner>/equicast-fx`). The
FX pairs config isn't baked in as the only input — pairs can also be passed
at runtime via `--pairs-json`, which is how the scheduled workflow feeds each
parallel chunk its share of the work (see below).

## Running the CLI locally

```bash
cd packages/fx
uv run equicast-fx --config config/fx_pairs.yaml --out ./output
uv run equicast-fx --pairs-json '[{"from":"GBP","to":"USD"}]' --out ./output
```

For each pair this writes:

- `fx=<PAIR>/profile.parquet` — one row, current snapshot
- `fx=<PAIR>/year=<YYYY>/price.parquet` — one row per trading day, for the
  current year only by default
- `fx=<PAIR>/metrics.parquet` — one row, volatility/Sharpe/drawdown/CAGR

Add `--full-load` to fetch each pair's entire available yfinance history for
**prices**, writing one `price.parquet` per year found (current year
included). It does not affect `metrics.parquet`, which always looks back far
enough for `cagr_10y` regardless of this flag:

```bash
uv run equicast-fx --pairs-json '[{"from":"GBP","to":"USD"}]' --out ./output --full-load
```

Profile, prices, and metrics are fetched as independent concurrent tasks per
pair (shared across one rate-limited `DatafeedClient`), tune with:

- `--max-workers` — profile/price/metrics fetches run concurrently, up to this many at once (default: 1)
- `--max-calls` / `--period-seconds` — shared rate limit, e.g. 5 calls per 1.0s (default: 1/1.0)

## Running the Docker image locally

```bash
docker build -f packages/fx/Dockerfile -t equicast-fx:local .
docker run --rm -v "$PWD/output:/output" equicast-fx:local \
  --pairs-json '[{"from":"GBP","to":"USD"}]' --out /output --full-load
```

## Manual smoke testing (`scripts/smoke_test.py`)

`packages/fx/scripts/smoke_test.py` exercises `FXClient.profile()`,
`.prices()`, and `MetricsClient.metrics()` against **live** Yahoo Finance
data — it's a manual QA tool, not part of the automated `pytest` suite (a
live-network test would make CI slow and flaky), so run it by hand whenever
you want to sanity-check the pipeline end to end.

```bash
cd packages/fx

# Defaults to every pair in config/fx_pairs.yaml, prints JSON to stdout
uv run python scripts/smoke_test.py

# Only specific pairs
uv run python scripts/smoke_test.py --pairs GBP:USD,EUR:GBP

# Write real Parquet files instead (exercises the writer functions too)
uv run python scripts/smoke_test.py --pairs GBP:USD --format parquet --out ./smoke_output

# Full historical load instead of current-year-only (applies to prices only)
uv run python scripts/smoke_test.py --pairs GBP:USD --format parquet --out ./smoke_output --full-load
```

In `--format json` mode, `profile` and `metrics` are printed in full and
`prices` is summarized (row count, date range, first/last row) rather than
dumped in full — a `--full-load` run can be 20+ years of daily rows.
`--format parquet` writes the real files via
`write_profile_parquet`/`write_price_parquet`/`write_metrics_parquet`, so
you can then inspect them with any Parquet reader (e.g. `pd.read_parquet`).

It also works inside the Docker image — same file is already copied in by
`packages/fx/Dockerfile` — by overriding the image's entrypoint:

```bash
docker build -f packages/fx/Dockerfile -t equicast-fx:local .
docker run --rm --entrypoint uv equicast-fx:local \
  run --no-sync python scripts/smoke_test.py --pairs GBP:USD

# Parquet mode needs a volume so the output survives the container:
docker volume create smoke-test-vol
docker run --rm --entrypoint uv -v smoke-test-vol:/smoke_output equicast-fx:local \
  run --no-sync python scripts/smoke_test.py --pairs GBP:USD --format parquet --out /smoke_output
docker run --rm -v smoke-test-vol:/smoke_output alpine find /smoke_output -type f
docker volume rm smoke-test-vol
```

Prefer a named Docker volume over a host bind mount for this on Windows —
Git Bash/PowerShell mangle bare absolute paths like `/smoke_output` passed to
`docker run` (a shell quirk, not a Docker or script issue).

## Deploying the infrastructure

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

This provisions:

- `equicast-market-data-<env>` S3 bucket (shared with the backend's on-demand
  cache) — FX data lands under `fx=<PAIR>/...` in this bucket
- A GitHub Actions OIDC IAM role scoped to `s3://equicast-market-data-<env>/fx=*/*`,
  so `fx-ingestion.yml` uploads without any long-lived AWS credentials

After applying, wire the outputs into the repo:

- Repo secret `AWS_FX_INGESTION_ROLE_ARN` = the `fx_ingestion_role_arn` Terraform output
- Repo variable `MARKET_DATA_BUCKET` = the bucket name (e.g. `equicast-market-data-prod`)
- Repo variable `AWS_REGION` (optional, defaults to `us-east-1`)

## Publishing the image

`fx-image.yml` builds and pushes `equicast-fx` to GHCR automatically on
changes to `packages/datafeed/` or `packages/fx/` on `main`, or on demand via
its `workflow_dispatch` trigger (Actions tab → *Build FX Image* → *Run
workflow*).

## Running the scheduled ingestion

`fx-ingestion.yml` runs every 6 hours (`cron: "0 */6 * * *"`) and can also be
triggered manually (Actions tab → *FX Ingestion* → *Run workflow*) with these
inputs:

| Input | Default | Meaning |
|---|---|---|
| `full_load` | `false` | Fetch each pair's entire history (all years) instead of just the current year |
| `chunk_size` | `300` | Target FX pairs per parallel chunk |
| `max_workers` | `5` | Concurrent fetches within each container |
| `max_calls` | `5` | Max yfinance calls per `period_seconds`, per container |
| `period_seconds` | `1.0` | Rate-limit window, in seconds, per container |

The workflow has two jobs:

1. **plan** — runs `equicast-fx-plan` to split the configured pairs into
   chunks, capped at 256 chunks (GitHub's per-workflow matrix job limit). If
   the pair list would need more than 256 chunks at the target `chunk_size`,
   the chunk size grows instead of pairs being dropped.
2. **ingest** — a matrix job (`max-parallel: 20`, tunable in the workflow
   file) with one leg per chunk: pulls the image, passes its chunk via
   `--pairs-json`, and uploads the resulting Parquet files to
   `s3://equicast-market-data-<env>/`. Each leg runs on its own GitHub-hosted
   runner (a separate source IP hitting Yahoo Finance), and each container
   also fetches its chunk's pairs (profile + prices + metrics) concurrently —
   so throughput scales both across and within legs.

With today's 4 configured pairs this collapses to a single chunk/leg; at
thousands of pairs it fans out automatically. A `full_load=true` run doesn't
change the chunking — it just makes each container fetch full history for
**prices** instead of year-to-date for the pairs it's assigned (`metrics`
always looks back as far as it needs, regardless of this flag).

### S3 layout produced

```
s3://equicast-market-data-<env>/
└── fx=GBPUSD/
    ├── profile.parquet
    ├── metrics.parquet
    ├── year=2003/price.parquet
    ├── year=2004/price.parquet
    ├── ...
    └── year=2026/price.parquet
```
