# ETF pipeline: deployment and execution

How the `equicast-etf` scheduled ingestion pipeline is built, deployed, and
run. Mirrors [stock-pipeline.md](stock-pipeline.md)'s structure — read that
first if you haven't; this only calls out where ETF differs. For local
package setup (installing deps, running unit tests), see
[local-setup.md](local-setup.md).

## Architecture

```
packages/etf/config/etfs.yaml       (the tickers to extract)
        │
        ▼
equicast-etf CLI  ── uses ──▶  equicast-datafeed (rate limiting + retries)
        │                              │
        │                              ▼
        │                       Yahoo Finance (yfinance)
        ▼
Parquet files (profile.parquet, price.parquet)
        │
        ▼
GitHub Actions (etf-ingestion.yml)  ──▶  S3 (s3://equicast-market-data-<env>/)
```

`packages/etf/Dockerfile` containerizes the CLI. `etf-image.yml` builds and
pushes it to GHCR as a **private** image (`ghcr.io/<owner>/equicast-etf`).
The ticker config isn't baked in as the only input — tickers can also be
passed at runtime via `--tickers-json`, which is how the scheduled workflow
feeds each parallel chunk its share of the work (see below).

**Only `profile()` and `prices()` are implemented so far** — no dividends,
events, or risk metrics yet, mirroring how `equicast-stock` itself started
out. `equicast-etf` also only depends on `equicast-datafeed`.

Expect a `WARNING` line near the top of every run's logs — a one-time (per
process) disclaimer from `equicast-datafeed`/`ETFClient` (data via
yfinance, educational use only). See the [README's disclaimer
section](../README.md#disclaimer) for the full text; this is expected, not
an error.

## Running the CLI locally

```bash
cd packages/etf
uv run equicast-etf --config config/etfs.yaml --out ./output
uv run equicast-etf --tickers-json '["VOO"]' --out ./output
```

For each ticker this writes:

- `etf=<TICKER>/profile.parquet` — one row: name, quote type, exchange,
  currency, description, category, fund family, website, beta, expense
  ratio, dividend rate/yield, total assets, NAV price, volume, day/year
  price range and moving averages, YTD/3yr/5yr average returns, inception
  date, last updated, source
- `etf=<TICKER>/year=<YYYY>/price.parquet` — one row per trading day, for
  the current year only by default: ticker, currency, date,
  open/high/low/close/average, last updated, source

See [packages/etf/README.md](../packages/etf/README.md) for the exact field
lists, including how the profile differs from `equicast-stock`'s and how
`website`/`beta`/`inception_date` are derived.

Add `--full-load` to fetch each ticker's entire available yfinance history
for **prices**, writing one `price.parquet` per year found (current year
included). It does not affect `profile.parquet`:

```bash
uv run equicast-etf --config config/etfs.yaml --out ./output --full-load
```

- `--max-workers` — profile/price fetches run concurrently, up to this many at once (default: 1)
- `--max-calls` / `--period-seconds` — shared rate limit, e.g. 5 calls per 1.0s (default: 1/1.0)

## Running the Docker image locally

```bash
docker build -f packages/etf/Dockerfile -t equicast-etf:local .
docker run --rm -v "$PWD/output:/output" equicast-etf:local \
  --tickers-json '["VOO"]' --out /output --full-load
```

## Manual smoke testing (`scripts/smoke_test.py`)

`packages/etf/scripts/smoke_test.py` exercises `ETFClient.profile()`,
`.prices()`, and the Parquet writers against **live** Yahoo Finance data —
it's a manual QA tool, not part of the automated `pytest` suite (a
live-network test would make CI slow and flaky), so run it by hand whenever
you want to sanity-check the pipeline end to end.

```bash
cd packages/etf

# Defaults to every ticker in config/etfs.yaml, prints JSON to stdout
uv run python scripts/smoke_test.py

# Only specific tickers
uv run python scripts/smoke_test.py --tickers VOO,QQQ

# Write real Parquet files instead (exercises the writer functions too)
uv run python scripts/smoke_test.py --tickers VOO --format parquet --out ./smoke_output

# Full historical load instead of current-year-only (applies to prices only)
uv run python scripts/smoke_test.py --tickers VOO --format parquet --out ./smoke_output --full-load
```

In `--format json` mode, `profile` is printed in full and `prices` is
summarized (row count, date range, first/last row) rather than dumped in
full — a `--full-load` run can be 20+ years of daily rows. `--format
parquet` writes the real files via `write_profile_parquet`/
`write_price_parquet`, so you can then inspect them with any Parquet reader
(e.g. `pd.read_parquet`).

It also works inside the Docker image — same file is already copied in by
`packages/etf/Dockerfile` — by overriding the image's entrypoint:

```bash
docker build -f packages/etf/Dockerfile -t equicast-etf:local .
docker run --rm --entrypoint uv equicast-etf:local \
  run --no-sync python scripts/smoke_test.py --tickers VOO

# Parquet mode needs a volume so the output survives the container:
docker volume create smoke-test-vol
docker run --rm --entrypoint uv -v smoke-test-vol:/smoke_output equicast-etf:local \
  run --no-sync python scripts/smoke_test.py --tickers VOO --format parquet --out /smoke_output
docker run --rm -v smoke-test-vol:/smoke_output alpine find /smoke_output -type f
docker volume rm smoke-test-vol
```

Prefer a named Docker volume over a host bind mount for this on Windows —
Git Bash/PowerShell mangle bare absolute paths like `/smoke_output` passed to
`docker run` (a shell quirk, not a Docker or script issue).

## Deploying the infrastructure

Shares `equicast-market-data-<env>` with `equicast-fx` and `equicast-stock`
(`fx=<PAIR>/...`, `stock=<TICKER>/...`, and `etf=<TICKER>/...` all land in
the same bucket) — no separate bucket or Terraform changes needed. See
[fx-pipeline.md's "Deploying the infrastructure"](fx-pipeline.md#deploying-the-infrastructure)
section for the one-time OIDC role and bucket setup; it already covers this
pipeline too (all AWS-touching workflows authenticate through the same
role, and the IAM policy's `equicast-*` resource wildcard already includes
the shared bucket).

Uses the same `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` repo
variables `fx-ingestion.yml`/`stock-ingestion.yml` use (see
fx-pipeline.md) — nothing extra to configure there either.

## Publishing the image

`etf-image.yml` builds and pushes `equicast-etf` to GHCR automatically on
changes to `packages/datafeed/` or `packages/etf/` on `main`, or on demand
via its `workflow_dispatch` trigger (Actions tab → *Build ETF Image* →
*Run workflow*).

## Running the scheduled ingestion

`etf-ingestion.yml` runs every 6 hours (`cron: "0 4,10,16,22 * * *"`) and
can also be triggered manually (Actions tab → *ETF Ingestion* → *Run
workflow*) with these inputs:

| Input | Default | Meaning |
|---|---|---|
| `environment` | `dev` | Which bucket to upload to — `dev` (`MARKET_DATA_BUCKET_DEV`) or `production` (`MARKET_DATA_BUCKET_PROD`). Ignored on the scheduled trigger — see below |
| `full_load` | `false` | Fetch each ticker's entire history (all years) of prices instead of just the current year |
| `chunk_size` | `300` | Target ETF tickers per parallel chunk |
| `max_workers` | `5` | Concurrent fetches within each container |
| `max_calls` | `5` | Max yfinance calls per `period_seconds`, per container |
| `period_seconds` | `1.0` | Rate-limit window, in seconds, per container |

**Deliberately offset from both `fx-ingestion.yml`'s schedule** (`0 */6 * * *`
— 00:00/06:00/12:00/18:00 UTC) **and `stock-ingestion.yml`'s** (`0 2,8,14,20
* * *`): ETF runs 4 hours after each FX run and 2 hours after each stock run
(04:00/10:00/16:00/22:00 UTC), so none of the three pipelines ever overlap
even if a run takes longer than expected — all three write into the same S3
bucket and pull from the same GHCR/Yahoo Finance rate limits.

The scheduled (cron) trigger always targets **production** — same reasoning
as `fx-ingestion.yml`/`stock-ingestion.yml`: there's no `environment` input
to read on a timer, and an unattended run every 6 hours should land in the
real bucket, not dev. The `environment` input only applies to manual
`workflow_dispatch` runs, where it defaults to `dev` so an ad-hoc run
doesn't write to production by accident.

The workflow has two jobs, structured identically to
`fx-ingestion.yml`/`stock-ingestion.yml`'s:

1. **plan** — runs `equicast-etf-plan` to split the configured tickers into
   chunks, capped at 256 chunks (GitHub's per-workflow matrix job limit). It
   also resolves the target environment/bucket once (schedule → `production`,
   dispatch → the `environment` input) and fails fast if the corresponding
   `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` variable isn't set.
2. **ingest** — a matrix job (`max-parallel: 20`, tunable in the workflow
   file) with one leg per chunk: pulls the image, passes its chunk via
   `--tickers-json`, and uploads the resulting Parquet files to
   `s3://equicast-market-data-<env>/` (the bucket the `plan` job resolved).

### S3 layout produced

```
s3://equicast-market-data-<env>/
└── etf=VOO/
    ├── profile.parquet
    ├── year=2025/price.parquet
    └── year=2026/price.parquet
```
