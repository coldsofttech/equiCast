# equicast-etf

Class-based ETF ticker market data extraction, built on
[equicast-datafeed](../datafeed/README.md).

## Disclaimer

Data is sourced via [yfinance](https://github.com/ranaroussi/yfinance)
(Yahoo Finance) for educational and informational purposes only. It is not
financial advice, and equicast makes no guarantee of its accuracy,
completeness, or timeliness. Do not use it as the sole basis for any
financial decision — verify independently and consult a qualified
professional.

Constructing an `ETFClient` logs this as a one-line warning the first time
it happens in a process (shared with `equicast-datafeed`'s own disclaimer,
so you won't see it twice).

## Usage

```python
from equicast_etf import ETFClient

client = ETFClient("VOO")
profile = client.profile()
# {
#     "ticker": "VOO",
#     "name": "Vanguard S&P 500 ETF",
#     "quote_type": "ETF",
#     "exchange": "PCX",
#     "currency": "USD",
#     "description": "The fund manager employs an indexing investment approach ...",
#     "category": "Large Blend",
#     "fund_family": "Vanguard",
#     "website": "https://www.vanguard.com",
#     "beta": 1.0,
#     "expense_ratio": 0.03,
#     "dividend_rate": None,
#     "dividend_yield": 0.0107,
#     "total_assets": 1686884319232,
#     "nav_price": 708.98,
#     "volume": 8067208,
#     "day_open": 709.39, "day_high": 712.6692, "day_low": 706.26,
#     "day_close": 707.24, "day_average": 709.4646,
#     "year_open": 588.29, "year_high": 716.39, "year_low": 578.46,
#     "year_close": 707.24, "year_average": 647.425,
#     "moving_average_50_days": 693.1996, "moving_average_200_days": 652.7322,
#     "ytd_return": 10.11602,
#     "three_year_average_return": 0.2217858,
#     "five_year_average_return": 0.1294499,
#     "inception_date": "2010-09-07T00:00:00+00:00",
#     "last_updated": "2026-08-28T20:00:00+00:00",
#     "source": "yfinance",
# }
```

`dividend_rate` is `None` for ETFs yfinance doesn't report a trailing
distribution amount for (seen on several bond/blend funds) — `dividend_yield`
can still be populated in that case.

### How this differs from `equicast-stock`'s profile

An ETF has no company behind it, so several of `StockClient.profile()`'s
fields don't apply and are replaced here:

| Stock field | Dropped because | ETF replacement |
|---|---|---|
| `sector`, `industry` | always `None` for ETFs in yfinance | `category` (e.g. "Large Blend", "Intermediate Core Bond") |
| `market_cap` | not a meaningful concept for a fund | `total_assets` (AUM) |
| `beta` | yfinance has no plain `beta` for ETFs | `beta` here is sourced from yfinance's `beta3Year` instead |
| `payout_ratio` | always `None` for ETFs | — |
| `ceos` | `companyOfficers`/`executiveTeam` are always empty for ETFs | — |
| `address`, `country`, `region`, `full_time_employees` | ETFs have no corporate HQ/headcount | — |
| `ipo_date` | no real "IPO" for a fund | `inception_date`, sourced from yfinance's `fundInceptionDate` |

New fields with no stock equivalent: `expense_ratio`, `nav_price`,
`ytd_return`, `three_year_average_return`, `five_year_average_return`.

### On `website`

yfinance never populates `website` for ETFs — confirmed empty across every
major issuer checked (Vanguard, iShares, Invesco, State Street, Schwab,
BlackRock). Rather than always returning `None`, `website` is looked up from
a small static `fund_family` → issuer-website map in `client.py`
(`_FUND_FAMILY_WEBSITES`), matched by a lowercase substring of `fund_family`
(not an exact match — the same issuer's `fundFamily` string varies by
ticker, e.g. `"iShares"` vs `"BlackRock Asset Management Ireland - ETF"` for
different BlackRock-issued funds). `None` if `fund_family` is missing or
doesn't match a known issuer. Unlike every other field, this is not sourced
from yfinance's `.info` — a genuine, if small, exception to `"source":
"yfinance"`.

### On `beta`

Sourced from yfinance's `beta3Year` (a 3-year monthly beta, yfinance's own
ETF-specific beta window), not computed by equicast — the same "pass through
whatever yfinance computes" approach `equicast-stock`'s `beta` field uses,
just from a different underlying yfinance field name. Reliably populated in
practice (present across every ETF checked while building this client).

### On `dividend_yield`

Sourced from yfinance's `yield` field, which reports a fraction (e.g.
`0.0107` for VOO) — deliberately not `dividendYield`, which yfinance reports
as **percentage points** for ETFs specifically (e.g. `1.07` for the same
ticker), an inconsistent scale that would silently break any consumer
expecting the same fraction convention `equicast-stock`'s `dividend_yield`
uses.

### On the price-range fields

`day_*`/`year_*`/`moving_average_*` work identically to
`equicast-stock`/`equicast-fx`: `day_close` is the live price; `year_*` uses
a trailing 52-week window (`year_open` from a `history(period="1y")` call,
everything else from yfinance's own `fiftyTwoWeekHigh`/`fiftyTwoWeekLow`);
`*_average` fields are the high/low midpoint, not a mean of daily closes;
`moving_average_50_days`/`moving_average_200_days` come straight from
yfinance's own 50/200-day averages. All rounded to 8 decimal places
(`equicast-datafeed`'s `round_value`), `None` wherever the underlying
yfinance field is missing.

### On `inception_date`

Sourced from yfinance's `fundInceptionDate` (epoch seconds) — populated for
every ETF checked while building this client. Falls back to
`firstTradeDateMilliseconds`/`firstTradeDateEpochUtc` (the first date
yfinance itself has trading data for this ticker) only if `fundInceptionDate`
is missing, the same fallback `equicast-stock`'s `ipo_date` uses. Formatted
as a full ISO 8601 datetime, same as `last_updated`.

## CLI

Reads the ETF tickers listed in a config file, fetches a profile, daily
prices, dividends, events, and metrics for each, and writes:

- `<out>/etf=<TICKER>/profile.parquet` — one row, current snapshot
- `<out>/etf=<TICKER>/year=<YYYY>/price.parquet` — one row per trading day,
  for the current year only by default
- `<out>/etf=<TICKER>/year=<YYYY>/dividend.parquet` — one row per
  ex-dividend date, for the current year only by default (empty for tickers
  with no dividend history)
- `<out>/etf=<TICKER>/year=<YYYY>/events.parquet` — one row per event
  (earnings report, analyst rating change, stock split), for the current
  year only by default. In practice only ever has `"split"` rows for an
  ETF — see [On `events.parquet`](#on-eventsparquet) below
- `<out>/etf=<TICKER>/metrics.parquet` — one row, `equicast-metrics`'
  risk/performance metrics only (volatility, Sharpe ratio, max drawdown,
  CAGR) — no valuation/fundamental metrics, unlike `equicast-stock`

```bash
uv run equicast-etf --config config/etfs.dev.yaml --out ./output
```

Add `--full-load` to fetch each ticker's entire available yfinance history
for prices, dividends, and events, writing one
`price.parquet`/`dividend.parquet`/`events.parquet` per year found (current
year included) — same as `equicast-stock`'s `--full-load`. It does not
affect `metrics.parquet`:

```bash
uv run equicast-etf --config config/etfs.dev.yaml --out ./output --full-load
```

`prices()` returns records shaped `{ticker, currency, date, open, high, low,
close, average, last_updated, source}` — `currency` comes from a
`get_info()` call (yfinance doesn't return it alongside `history()`'s OHLC
data).

### On `events.parquet`

Written from [`equicast-events`](../events/README.md)' `EventsClient` — a
generic client (not part of `ETFClient`), the same one `equicast-stock`
uses, built so it's reusable across asset classes.

Records are shaped `{ticker, event_type, date, eps_estimate, reported_eps,
surprise_pct, firm, from_grade, to_grade, action, ratio, last_updated,
source}`, combining three distinct event types into one file per year —
`event_type` says which, and only that type's fields are populated (the
rest `None`). **In practice, an ETF ticker only ever produces `"split"`
rows here**: `EventsClient` still fetches earnings dates and analyst
ratings the same way it does for a stock, but yfinance has no earnings
reports or analyst coverage for a fund, so those two event types
contribute nothing — checked live for all 5 configured tickers before
relying on this. Splits are real, though: VOO (2013), QQQ (2000, 2-for-1),
and VTI (2008, 2-for-1) each have exactly one in their full yfinance
history; AGG and GLD have none. Tickers/years with no events simply
produce no `events.parquet` file, same as `equicast-stock`.

### On `metrics.parquet`

Only `MetricsClient.metrics()` — volatility, Sharpe ratio, max drawdown,
CAGR (1/2/3/5/10-year) — works the same way as for a stock ticker or FX pair
(see [equicast-metrics's README](../metrics/README.md)). Deliberately
**not** `.fundamentals()`, unlike `equicast-stock`: its valuation ratios
(PE, EPS, PEG, price-to-book/sales, EV/EBITDA, margins, ROE/ROA,
debt-to-equity, FCF/share) are earnings/balance-sheet-based and stock-only.
Checked live against VOO/QQQ/AGG/GLD before deciding this — 12-13 of its 15
fields came back `None` for every one of them, and the few that didn't
(`trailing_pe`, `price_to_book`) were an inconsistent yfinance
aggregate-portfolio figure, present for some ETFs and absent for others
with no clear pattern, not a genuine per-fund fundamental worth publishing.
The fund-level figures that matter for an ETF — expense ratio, NAV, AUM,
category, YTD/3yr/5yr returns — already live in `profile.parquet` (see
above), so there's no gap for a `fundamentals()`-style tier to fill here.

### On `dividend.parquet`

Written from [`equicast-dividends`](../dividends/README.md)'
`DividendsClient` — a generic client (not part of `ETFClient`), the same one
`equicast-stock` uses, built so it's reusable across asset classes rather
than living inside either package.

Records are shaped `{ticker, currency, ex_dividend_date, price,
last_updated, source}`. `price` is the dividend cash amount per share, not
an ETF price. There's no `payment_date` field — yfinance's dividend history
only has ex-dividend date and amount, for any ticker, at any point in
history; see equicast-dividends's README for details. Tickers with no
dividend history (e.g. `GLD`, a gold trust that pays no distribution)
simply produce no `dividend.parquet` file for that year.

## Configuration

`config/etfs.dev.yaml` and `config/etfs.prod.yaml` each list the ETF tickers
to extract for that environment (currently VOO, QQQ, VTI, AGG, GLD in both —
a mix of broad-market, tech-growth, bond, and commodity funds across
different issuers, for category diversity — `etf-ingestion.yml` picks
between them, see [docs/etf-pipeline.md](../../docs/etf-pipeline.md)).

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
