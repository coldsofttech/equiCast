# equicast-events

Generic corporate events — earnings reports, analyst rating changes, and
stock splits — for any yfinance equity-like symbol: a stock ticker (`AAPL`)
today, an ETF ticker in the future, since the underlying data is shaped the
same way regardless of asset class. Mirrors `equicast-dividends`'
`DividendsClient` and `equicast-metrics`' `MetricsClient` in spirit: a small,
generic client built on `equicast-datafeed`, reusable by any asset-class
package rather than living inside one.

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

Constructing an `EventsClient` logs this as a one-line warning the first
time it happens in a process. Like `equicast-dividends`, this uses its own
distinct message rather than reusing `equicast-datafeed`'s — so it's always
visible even when `DatafeedClient`'s disclaimer already fired earlier in the
same process (e.g. constructed first in a CLI's `run()`).

## Usage

```python
from equicast_events import EventsClient

EventsClient("AAPL").events()
# [{"ticker": "AAPL", "event_type": "earnings", "date": "2026-01-30",
#   "eps_estimate": None, "reported_eps": 2.18, "surprise_pct": -3.5,
#   "firm": None, "from_grade": None, "to_grade": None, "action": None,
#   "ratio": None, "last_updated": "2026-08-30T09:00:00+00:00", "source": "yfinance"},
#  {"ticker": "AAPL", "event_type": "rating", "date": "2026-03-01",
#   "eps_estimate": None, "reported_eps": None, "surprise_pct": None,
#   "firm": "Morgan Stanley", "from_grade": "Equal-Weight", "to_grade": "Overweight",
#   "action": "up", "ratio": None, "last_updated": "2026-08-30T09:00:00+00:00",
#   "source": "yfinance"},
#  {"ticker": "AAPL", "event_type": "split", "date": "2026-06-09",
#   "eps_estimate": None, "reported_eps": None, "surprise_pct": None,
#   "firm": None, "from_grade": None, "to_grade": None, "action": None,
#   "ratio": 4.0, "last_updated": "2026-08-30T09:00:00+00:00", "source": "yfinance"}]
```

One record per event, combining three distinct kinds into a single list
rather than three separate methods — each record's `event_type`
(`"earnings"` / `"rating"` / `"split"`) says which, and only that type's
fields are populated (everything else is `None`). By default covers this
calendar year to date, plus any future-dated entries (`date >= this year`,
not `== this year`) — only earnings ever has any (estimated future report
dates); rating changes and splits are purely historical, so this is a no-op
for them. `events(full_load=True)` covers this symbol's entire available
history instead, future entries included either way — same
year-to-date/full-history split as `DividendsClient.dividends()`/
`StockClient.prices()`, even though none of the three underlying yfinance
calls has a period parameter of its
own.

A symbol with no events of a given kind (no upcoming/reported earnings, no
analyst coverage, no stock splits) simply omits that kind's records; a
symbol with none of the three returns `[]`.

### On `earnings` records

`eps_estimate`/`reported_eps`/`surprise_pct` come from yfinance's earnings
calendar. Future/not-yet-reported dates have `reported_eps`/`surprise_pct`
still `None` (only `eps_estimate` populated); already-reported dates have
all three. Depth is controlled by a row-count `limit` (yfinance has no
date-range parameter here) — `EARNINGS_DEFAULT_LIMIT` (12) normally,
`EARNINGS_FULL_LOAD_LIMIT` (100, yfinance's own hard cap) with
`full_load=True`. `surprise_pct` is yfinance's raw percentage-point value
(e.g. `-3.5` for -3.5%), not normalized to a 0–1 fraction.

### On `rating` records

`firm`/`from_grade`/`to_grade`/`action` come from yfinance's full
upgrade/downgrade history — inherently a historical log (each row is a past
rating-change event), so there's no forward-looking equivalent the way
earnings has estimated future rows. `from_grade` is `None` for a coverage
initiation (yfinance reports an empty string there, not a grade).

### On `split` records

`ratio` is yfinance's raw split ratio (e.g. `4.0` for a 4-for-1 split, `0.5`
for a 1-for-2 reverse split), not further interpreted.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
