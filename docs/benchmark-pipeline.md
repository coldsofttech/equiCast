# Benchmark pipeline: deployment and execution

How the `equicast-benchmark` scheduled ingestion pipeline is built,
deployed, and run. For local package setup (installing deps, running unit
tests), see [local-setup.md](local-setup.md). For what the
`profile`/`price`/`metrics` data actually contains, see the root
[README](../README.md).

## Architecture

```
packages/benchmark/config/benchmarks.dev.yaml   (dev: the benchmarks to extract)
packages/benchmark/config/benchmarks.prod.yaml  (production: the benchmarks to extract)
        │
        ▼
equicast-benchmark CLI  ── uses ──▶  equicast-datafeed (rate limiting + retries)
        │                     └────▶  equicast-metrics (volatility, Sharpe, drawdown, CAGR)
        │                                     │
        │                                     ▼
        │                              Yahoo Finance (yfinance)
        ▼
Parquet files (profile.parquet, price.parquet, metrics.parquet)
        │
        ▼
GitHub Actions (benchmark-ingestion.yml)  ──▶  S3 (s3://equicast-market-data-<env>/)
```

`packages/benchmark/Dockerfile` containerizes the CLI. `benchmark-image.yml`
builds and pushes it to GHCR as a **private** image
(`ghcr.io/<owner>/equicast-benchmark`). The benchmark config isn't baked in
as the only input — benchmarks can also be passed at runtime via
`--benchmarks-json`, which is how the scheduled workflow feeds each parallel
chunk its share of the work (see below). The image's default `CMD` points
at `config/benchmarks.dev.yaml`; `benchmark-ingestion.yml` never relies on
that default — it resolves `dev`/`prod` itself and always passes
`--benchmarks-json` explicitly.

Expect two `WARNING` lines near the top of every run's logs — a one-time
(per process) disclaimer from `equicast-datafeed` (data via yfinance,
educational use only) and one from `equicast-metrics` (metrics calculated by
equicast, not independently verified). See the [README's disclaimer
section](../README.md#disclaimer) for the full text; this is expected, not
an error.

A benchmark is a single yfinance symbol (like a stock ticker), not a pair
(like FX) — so `equicast-benchmark` has no dividends and no fundamentals,
the same reasoning `equicast-fx` uses (an index pays none and has no
earnings/balance sheet). `key` (e.g. `"SP500"`) is a stable, human-readable
S3 partition identifier you choose; `symbol` (e.g. `"^GSPC"`) is the exact
yfinance ticker to fetch — see `packages/benchmark/config/benchmarks.prod.yaml`
for the full list.

## Running the CLI locally

```bash
cd packages/benchmark
uv run equicast-benchmark --config config/benchmarks.dev.yaml --out ./output
uv run equicast-benchmark --benchmarks-json '[{"key":"SP500","symbol":"^GSPC"}]' --out ./output
```

For each benchmark this writes:

- `benchmark=<KEY>/profile.parquet` — one row, current snapshot
- `benchmark=<KEY>/price/current.parquet` — one row per trading day, for the
  current year only by default
- `benchmark=<KEY>/metrics.parquet` — one row, volatility/Sharpe/drawdown/CAGR

Add `--full-load` to fetch each benchmark's entire available yfinance
history for **prices**, additionally writing
`benchmark=<KEY>/price/history.parquet` — every year before the current one,
combined into that one file rather than split per year
(`price/current.parquet` still gets just the current year). It does not
affect `metrics.parquet`, which always looks back far enough for `cagr_10y`
regardless of this flag:

```bash
uv run equicast-benchmark --benchmarks-json '[{"key":"SP500","symbol":"^GSPC"}]' --out ./output --full-load
```

Profile, prices, and metrics are fetched as independent concurrent tasks per
benchmark (shared across one rate-limited `DatafeedClient`), tune with:

- `--max-workers` — profile/price/metrics fetches run concurrently, up to this many at once (default: 1)
- `--max-calls` / `--period-seconds` — shared rate limit, e.g. 5 calls per 1.0s (default: 1/1.0)

## Running the Docker image locally

```bash
docker build -f packages/benchmark/Dockerfile -t equicast-benchmark:local .
docker run --rm -v "$PWD/output:/output" equicast-benchmark:local \
  --benchmarks-json '[{"key":"SP500","symbol":"^GSPC"}]' --out /output --full-load
```

## Manual smoke testing (`scripts/smoke_test.py`)

`packages/benchmark/scripts/smoke_test.py` exercises
`BenchmarkClient.profile()`, `.prices()`, and `MetricsClient.metrics()`
against **live** Yahoo Finance data — it's a manual QA tool, not part of the
automated `pytest` suite (a live-network test would make CI slow and
flaky), so run it by hand whenever you want to sanity-check the pipeline
end to end.

```bash
cd packages/benchmark

# Defaults to every benchmark in config/benchmarks.dev.yaml, prints JSON to stdout
uv run python scripts/smoke_test.py

# Only specific benchmarks
uv run python scripts/smoke_test.py --benchmarks SP500:^GSPC,DAX:^GDAXI

# Write real Parquet files instead (exercises the writer functions too)
uv run python scripts/smoke_test.py --benchmarks SP500:^GSPC --format parquet --out ./smoke_output

# Full historical load instead of current-year-only (applies to prices only)
uv run python scripts/smoke_test.py --benchmarks SP500:^GSPC --format parquet --out ./smoke_output --full-load
```

In `--format json` mode, `profile` and `metrics` are printed in full and
`prices` is summarized (row count, date range, first/last row) rather than
dumped in full — a `--full-load` run can be 20+ years of daily rows.
`--format parquet` writes the real files via
`write_profile_parquet`/`write_price_parquet`/`write_metrics_parquet`, so
you can then inspect them with any Parquet reader (e.g. `pd.read_parquet`).

## Deploying the infrastructure

One-time prerequisite: create the OIDC provider and IAM role
`terraform.yml`/`deploy.yml`/`benchmark-ingestion.yml` all authenticate to
AWS through — see
[aws-github-oidc-setup.md](aws-github-oidc-setup.md) for the exact steps.

Second one-time prerequisite: the state bucket `equicast-tf-state`
must exist before `terraform init` will succeed — see
[terraform-state-setup.md](terraform-state-setup.md).

Once that role exists and the `AWS_ROLE_ARN` repo secret is set, deploy the
rest of the infrastructure — see [the FX pipeline docs' "Deploying the
infrastructure"](fx-pipeline.md#deploying-the-infrastructure) for the exact
commands; the same `equicast-market-data-<env>` S3 bucket is shared by
every asset class, benchmark data lands under `benchmark=<KEY>/...` in it,
and the same `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` repo
variables `benchmark-ingestion.yml` reads already need to exist for
FX/stock/ETF.

## Publishing the image

`benchmark-image.yml` builds and pushes `equicast-benchmark` to GHCR
automatically on changes to `packages/datafeed/` or `packages/benchmark/`
on `main`, or on demand via its `workflow_dispatch` trigger (Actions tab →
*Build Benchmark Image* → *Run workflow*).

## Running the scheduled ingestion

`benchmark-ingestion.yml` runs once daily, Monday-Friday, at 23:00 UTC
(`cron: "0 23 * * 1-5"`) — 15 minutes after `stock-ingestion.yml` (itself
offset from `fx-ingestion.yml`/`etf-ingestion.yml`, see
[fx-pipeline.md](fx-pipeline.md#running-the-scheduled-ingestion)), so none
of the four ever overlap. Unlike `etf-ingestion.yml`/`stock-ingestion.yml`,
there's no Saturday entry — `equicast-benchmark` has no *dividend*
forecasting step (indices pay no dividends), so there was nothing for a
weekly run to do here. Issue #68 (see [Forecasting](#forecasting) below)
added *price-band* forecasting, but it's not yet wired into this workflow
either. Can also be triggered manually (Actions tab → *Benchmark
Ingestion* → *Run workflow*, any day) with these inputs:

| Input | Default | Meaning |
|---|---|---|
| `environment` | `dev` | Which bucket to upload to — `dev` (`MARKET_DATA_BUCKET_DEV`) or `production` (`MARKET_DATA_BUCKET_PROD`). Ignored on the scheduled trigger — see below |
| `full_load` | `false` | Fetch each benchmark's entire history (all years) instead of just the current year |
| `chunk_size` | `300` | Target benchmarks per parallel chunk |
| `max_workers` | `5` | Concurrent fetches within each container |
| `max_calls` | `5` | Max yfinance calls per `period_seconds`, per container |
| `period_seconds` | `1.0` | Rate-limit window, in seconds, per container |

The scheduled (cron) trigger always targets **production** — there's no
`environment` input to read on a timer, and a data feed running unattended
once a weekday should land in the real bucket, not dev. The `environment`
input only applies to manual `workflow_dispatch` runs, where it defaults to
`dev` so an ad-hoc run doesn't write to production by accident.

The workflow has three jobs — **plan**, **ingest**, and **build-catalog** —
with the exact same responsibilities as `fx-ingestion.yml`'s (see
[fx-pipeline.md](fx-pipeline.md#running-the-scheduled-ingestion) for the
full breakdown of each), just against `equicast-benchmark`/`benchmarks.dev.yaml`/
`benchmarks.prod.yaml`/`catalog/benchmark.parquet` instead.

With today's 15 configured production benchmarks (5 in dev) this collapses
to a single chunk/leg; at hundreds of benchmarks it fans out automatically.

### S3 layout produced

```
s3://equicast-market-data-<env>/
├── catalog/
│   └── benchmark.parquet
└── benchmark=SP500/
    ├── profile.parquet
    ├── metrics.parquet
    └── price/
        ├── history.parquet   (written once by a --full-load run)
        └── current.parquet   (rewritten by every run)
```

## Forecasting

GitHub issue #68 added `equicast-forecasting` support for benchmarks —
`--asset-class benchmark --forecast-kind price-bands` — routing each
configured benchmark's own `key` (e.g. `SP500`) to one of its per-index
schemas and writing `benchmark=<KEY>/forecasting/price_bands.parquet`. Not
wired into this workflow's scheduled runs; see
[packages/forecasting/README.md](../packages/forecasting/README.md#benchmark-price-band-forecasting)
for the full model. `--forecast-kind dividends` still doesn't apply here —
indices pay no dividends.
