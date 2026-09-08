# Watchlist pipeline: deployment and execution

How the `equicast-watchlist` scheduled pipeline is built, deployed, and
run. For local package setup (installing deps, running unit tests), see
[local-setup.md](local-setup.md). For what a system watchlist's `entries`
data actually contains, see the root [README](../README.md).

## How this differs from fx/stock/etf/benchmark/future

Every other ingestion pipeline fetches its own instruments from yfinance
and writes `<asset_class>=<TICKER>/{profile,metrics,price}.parquet` (three
files per instrument). `equicast-watchlist` is different in three ways:

1. **It reads nothing from S3.** Each configured entry is fetched fresh
   from yfinance via its own package's Client class
   (`equicast_fx.FXClient`/`equicast_future.FutureClient`/
   `equicast_benchmark.BenchmarkClient`) — it never depends on
   fx/future/benchmark-ingestion.yml having already published anything for
   that symbol, and has no ordering relationship with any of them.
2. **It writes one file per watchlist, not per instrument.** All of a
   watchlist's entries land as rows in a single
   `watchlist=<KEY>/entries.parquet`.
3. **It runs weekly, not daily.** A system watchlist is a periodic
   snapshot, not a live feed — see "Running the scheduled ingestion" below.

## Architecture

```
packages/watchlist/config/global_markets.dev.yaml   (dev: the watchlist's entries)
packages/watchlist/config/global_markets.prod.yaml  (production: the watchlist's entries)
        │
        ▼
equicast-watchlist CLI  ── uses ──▶  equicast-fx / equicast-future / equicast-benchmark
        │                                     │
        │                                     ▼
        │                              Yahoo Finance (yfinance)
        ▼
One Parquet file (entries.parquet)
        │
        ▼
GitHub Actions (watchlist-ingestion.yml)  ──▶  S3 (s3://equicast-market-data-<env>/)
```

`packages/watchlist/Dockerfile` containerizes the CLI. `watchlist-image.yml`
builds and pushes it to GHCR as a **private** image
(`ghcr.io/<owner>/equicast-watchlist`). The image's default `CMD` points at
`config/global_markets.dev.yaml`; `watchlist-ingestion.yml` never relies on
that default — it resolves `dev`/`prod` itself and always passes
`--config` explicitly.

Expect a `WARNING` line near the top of every run's logs — a one-time (per
process) disclaimer from whichever of equicast-fx/-future/-benchmark
constructs its Client first (shared text, so constructing all three in one
process only logs it once — see `equicast_datafeed.disclaimers.warn_once`).
See the [README's disclaimer section](../README.md#disclaimer) for the
full text; this is expected, not an error.

Each entry's `current_price` is always in that instrument's own native
currency — a system watchlist has no single owner to convert it for, unlike
a real holding. `change_1w_pct`/`change_1m_pct` are computed from one
month of daily closes fetched alongside the profile (`change_1m_pct`
against the oldest row in that window, `change_1w_pct` against the row 5
trading days back) — either comes back `None` when there isn't enough
published history yet for a symbol, rather than failing the whole run.

## Running the CLI locally

```bash
cd packages/watchlist
uv run equicast-watchlist --watchlist-key GLOBAL_MARKETS --config config/global_markets.dev.yaml --out ./output
```

This writes `output/watchlist=GLOBAL_MARKETS/entries.parquet` — one row
per configured instrument.

Entries are fetched as independent concurrent tasks (shared across one
rate-limited `DatafeedClient`), tune with:

- `--max-workers` — entries fetched concurrently, up to this many at once (default: 1)
- `--max-calls` / `--period-seconds` — shared rate limit, e.g. 5 calls per 1.0s (default: 1/1.0)

## Running the Docker image locally

```bash
docker build -f packages/watchlist/Dockerfile -t equicast-watchlist:local .
docker run --rm -v "$PWD/output:/output" equicast-watchlist:local \
  --watchlist-key GLOBAL_MARKETS --config config/global_markets.dev.yaml --out /output
```

## Deploying the infrastructure

One-time prerequisite: create the OIDC provider and IAM role
`terraform.yml`/`deploy.yml`/`watchlist-ingestion.yml` all authenticate to
AWS through — see [aws-github-oidc-setup.md](aws-github-oidc-setup.md) for
the exact steps.

Second one-time prerequisite: the state bucket `equicast-tf-state`
must exist before `terraform init` will succeed — see
[terraform-state-setup.md](terraform-state-setup.md).

Once that role exists and the `AWS_ROLE_ARN` repo secret is set, deploy the
rest of the infrastructure — see [the FX pipeline docs' "Deploying the
infrastructure"](fx-pipeline.md#deploying-the-infrastructure) for the exact
commands; the same `equicast-market-data-<env>` S3 bucket is shared by
every asset class, watchlist data lands under `watchlist=<KEY>/...` in it,
and the same `MARKET_DATA_BUCKET_DEV`/`MARKET_DATA_BUCKET_PROD` repo
variables `watchlist-ingestion.yml` reads already need to exist for
FX/stock/ETF/benchmark/future.

## Publishing the image

`watchlist-image.yml` builds and pushes `equicast-watchlist` to GHCR
automatically on changes to `packages/datafeed/`, `packages/fx/`,
`packages/benchmark/`, `packages/future/`, or `packages/watchlist/` on
`main`, or on demand via its `workflow_dispatch` trigger (Actions tab →
*Build Watchlist Image* → *Run workflow*).

## Running the scheduled ingestion

`watchlist-ingestion.yml` runs once weekly, **Saturday only**, at 06:00 UTC
(`cron: "0 6 * * 6"`) — unlike every other ingestion workflow (all
Monday-Friday), a system watchlist is a periodic snapshot rather than a
daily feed, and Saturday gives it a full week's trading (through Friday's
close) to summarize. Since `equicast-watchlist` fetches straight from
yfinance itself rather than reading any other pipeline's S3 output, it has
no ordering dependency on fx/stock/etf/benchmark/future-ingestion.yml and
no reason to run on their schedule. Can also be triggered manually (Actions
tab → *Watchlist Ingestion* → *Run workflow*, any day) with these inputs:

| Input | Default | Meaning |
|---|---|---|
| `environment` | `dev` | Which bucket to upload to — `dev` (`MARKET_DATA_BUCKET_DEV`) or `production` (`MARKET_DATA_BUCKET_PROD`). Ignored on the scheduled trigger — see below |
| `max_workers` | `5` | Concurrent fetches within each container |
| `max_calls` | `5` | Max yfinance calls per `period_seconds`, per container |
| `period_seconds` | `1.0` | Rate-limit window, in seconds, per container |

The scheduled (cron) trigger always targets **production** — there's no
`environment` input to read on a timer. The `environment` input only
applies to manual `workflow_dispatch` runs, where it defaults to `dev` so
an ad-hoc run doesn't write to production by accident.

The workflow has one job, **ingest**, with one step per system
watchlist — today just "Build Global Markets watchlist entries". Unlike
fx/stock/etf/benchmark/future-ingestion.yml, there's no "plan" job
splitting work into matrix chunks (a system watchlist's entry list is
small enough to fetch in a single container run) and no "build-catalog"
job (`equicast-watchlist` doesn't produce or read a `catalog/*.parquet`
file at all). Adding a second system watchlist later means adding another
step here, each with its own config file — no new job, no changes to the
steps already there.

### S3 layout produced

```
s3://equicast-market-data-<env>/
└── watchlist=GLOBAL_MARKETS/
    └── entries.parquet
```
