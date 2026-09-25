# equicast-watchlist

Builds a system watchlist's entries — fx pairs, futures, and benchmarks —
fresh from yfinance each run, built on top of
[equicast-fx](../fx/README.md), [equicast-benchmark](../benchmark/README.md),
and [equicast-future](../future/README.md).

Unlike those three (and equicast-stock/-etf), this package never reads
anything from S3 — every entry is fetched live via its own package's
Client class, so a system watchlist's freshness doesn't depend on any
other pipeline having run first.

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

## Usage

```python
from pathlib import Path

from equicast_datafeed import DatafeedClient
from equicast_watchlist import build_entries, load_watchlist_entries

entries = load_watchlist_entries(Path("config/global_markets.dev.yaml"))
rows = build_entries(entries, DatafeedClient())
# [{"asset_class": "future", "ticker": "GOLD", "symbol": "GC=F",
#   "name": "Gold", "currency": "USD", "current_price": 2440.3,
#   "change_1w_pct": 1.2, "change_1m_pct": -0.4,
#   "last_updated": "2026-08-28T21:29:05+00:00", "source": "yfinance"},
#  ...]
```

`current_price` is always in the instrument's own native currency — a
system watchlist has no single owner to convert it for, unlike a real
holding. `change_1w_pct`/`change_1m_pct` are computed from one month of
daily closes (`change_1m_pct` against the oldest row, `change_1w_pct`
against the row 5 trading days back) — either comes back `None` when
there isn't enough published history yet for that symbol, rather than
raising.

## CLI

Reads a watchlist's entries listed in a config file, fetches each fresh
from yfinance, and writes one Parquet file:
`<out>/watchlist=<KEY>/entries.parquet`:

```bash
uv run equicast-watchlist --watchlist-key GLOBAL_MARKETS --config config/global_markets.dev.yaml --out ./output
```

## Configuration

`config/global_markets.dev.yaml` and `config/global_markets.prod.yaml`
each list the Global Markets watchlist's instruments for that environment
(`watchlist-ingestion.yml` picks between them) — see
`global_markets.prod.yaml`'s header comment for the per-`asset_class`
shape (`fx` takes `from`/`to`; `future`/`benchmark` take `key`/`symbol`,
matching those packages' own configs).

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
