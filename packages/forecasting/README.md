# equicast-forecasting

Projects a symbol's future dividend payouts from its actual dividend
history, built on [equicast-dividends](../dividends/README.md); daily FX
price probability bands from actual price history plus whatever real
interest-rate data is available (see
[FX price-band forecasting](#fx-price-band-forecasting)); daily,
sector-routed stock price probability bands from actual price/fundamentals
data (see [Stock price-band forecasting](#stock-price-band-forecasting));
daily, ETF-type-routed price probability bands from actual price/fund
data (see [ETF price-band forecasting](#etf-price-band-forecasting));
daily, per-index-routed price probability bands for market benchmarks
from actual index price history (see
[Benchmark price-band forecasting](#benchmark-price-band-forecasting));
and daily, commodity-class-routed price probability bands for futures
contracts from actual futures price history (see
[Futures price-band forecasting](#futures-price-band-forecasting)).

## Dividend forecasting

### Usage

```python
from equicast_dividends import DividendsClient
from equicast_forecasting import dividends

history = DividendsClient("AAPL").dividends(full_load=True)
dividends(history)
# [{"ticker": "AAPL", "currency": "USD", "ex_dividend_date": "2026-05-12",
#   "price": 0.26, "dividend_frequency": "quarterly",
#   "last_updated": "2026-08-30T09:00:00+00:00", "source": "equicast"},
#  ...]
```

`dividends(records, years=10)` takes a symbol's dividend records — the same
shape `DividendsClient.dividends()` returns — and projects up to `years`
years of future payouts forward from them. Returns `[]` when there isn't a
dependable cadence to extend: the same `"irregular"`/`"not_applicable"`
cases [`equicast-dividends`' `dividend_frequency()`](../dividends/README.md#dividend_frequency)
flags (a genuinely erratic payer, or fewer than 2 recorded payouts) aren't
projected forward — a classification this uncertain about the *past*
shouldn't be extrapolated years into the *future*.

Each returned record is shaped like a real dividend record (`ticker`,
`currency`, `ex_dividend_date`, `price`, `last_updated`, `source`), plus a
`dividend_frequency` field naming the cadence assumption used. `source` is
always `"equicast"`, never `"yfinance"` — this is a computed projection, not
observed data.

### How the dates are projected

Each projected payout continues the ticker's *actual* empirical cadence
forward from its most recent real payout —
[`median_payout_gap_days()`](../dividends/README.md#median_payout_gap_days),
the same day-gap `dividend_frequency()` classifies, not a fixed per-label
constant. A payer whose real median gap is 84 days keeps stepping by 84, not
by "quarterly"'s canonical ~91 — so the projected calendar doesn't
gradually drift away from the ticker's real one.

### How the amounts are projected

Every projected payout starts from the most recent *actual* amount, then
compounds once per calendar year crossed (relative to that last actual
payout) at a trailing dividend growth rate:

1. Sum actual payouts into one total per *complete* calendar year — the
   current year is excluded (it may not be complete yet), and so is any
   earlier year with fewer payouts than the cadence expects (52/12/4/2/1 for
   weekly/monthly/quarterly/half_yearly/yearly): typically the payer's first
   year, if dividends started partway through it. Comparing a partial first
   year against a later full year would manufacture a growth rate out of
   when the payer started paying, not out of how its dividend actually grew
   — this is what previously made a newly-initiated payer (started mid-year,
   one full year on the books since) look like it was compounding at ~35-40%
   a year.
2. Compare the oldest to the newest of the most recent 6 such years (5
   year-over-year steps) as a CAGR: `(newest / oldest) ** (1 / years) - 1`.
3. Clamp the result to ±50%/year, so one outlier historical year (a special
   dividend inflating a single year's total, or a one-off cut) can't produce
   an implausible runaway compound over a long horizon.
4. Fall back to `0.0` (flat — every projected payout repeats the last actual
   amount) if there are fewer than 2 complete years to compare, or the older
   year's total is `0`.

This is a projection from historical *rate*, not a prediction of specific
future dividend announcements — treat it as "if this ticker's recent cadence
and growth trend continue unchanged," not as authoritative. It will be
visibly wrong around any real dividend cut, suspension, or cadence change,
same as any trend extrapolation.

## FX price-band forecasting

Implements [GitHub issue #65](https://github.com/coldsofttech/equiCast/issues/65):
one daily probability band (10th/50th/90th percentile — not a point
forecast) per FX pair, out to `years` years, built from three horizon
regimes:

| Horizon | Model | Drift source |
|---|---|---|
| 1w–1m ("short") | GARCH/EWMA volatility, no directional drift | none — a pure random walk, on purpose (see below) |
| 6m–2y ("medium") | Interest-rate parity | a real `rate_diff` when available (see [Data coverage](#data-coverage)), else 0.0 |
| 3y–10y ("long") | PPP mean-reversion | `reer_deviation`, if a caller supplies one — always `None` today, see [Data coverage](#data-coverage) |

Each regime's drift tapers linearly into the next over 90 days rather than
jumping discontinuously at the boundary — cosmetic only, it doesn't change
either regime's own eventual drift level.

### Usage

```python
from equicast_forecasting import fx_price_bands

# `prices` needs at least `date`/`close` keys per record — the shape
# equicast_fx.FXClient.prices() already returns.
fx_price_bands(prices, "GBP", "USD", years=10)
# [{"from_currency": "GBP", "to_currency": "USD", "date": "2026-09-10",
#   "p10": 1.24, "p50": 1.32, "p90": 1.41, "regime": "short",
#   "volatility_model": "garch", "last_updated": "2026-09-09T09:00:00+00:00",
#   "source": "equicast"}, ...]
```

One row per *calendar* day (not just trading days, unlike real price
history) — this is a smooth theoretical band meant to extend a price chart
forward, not observed data, so there's no reason to gap it over weekends.
`volatility_model` (`"garch"`/`"ewma"` — see below) is the same for every
row, since volatility is estimated once from the whole history, not
per-day; `regime` varies by day, naming which of the three rows above
produced that day's drift.

### Why a pure random walk at the short horizon

The issue is explicit that GARCH/EWMA is a *volatility* forecast, paired
with a random walk for the actual price range — "not a directional return
forecast." So the short regime's median (`p50`) stays flat at the last
known price; only the band width grows (with `sqrt(days)`, the standard
i.i.d.-daily-returns assumption), via [`bands.price_bands()`](src/equicast_forecasting/bands.py).

### Volatility: GARCH(1,1) with an EWMA fallback

[`volatility.estimate_daily_volatility()`](src/equicast_forecasting/volatility.py)
tries a real zero-mean GARCH(1,1) fit (via the [`arch`](https://arch.readthedocs.io/)
package) first, falling back to a RiskMetrics-style EWMA estimate
(λ=0.94) when there's too little history (under 250 daily returns) or the
fit doesn't converge — GARCH fitting is numerically finicky on short or
unusually quiet series, and this package never raises for that, only
degrades.

### Data coverage

The issue's medium/long-horizon models call for macro inputs equicast has
no real data source for today: `inflation_diff`, `current_account_balance`,
`reer_deviation`, `productivity_diff`, `terms_of_trade_trend`,
`sovereign_debt_trend`. Rather than skip the medium/long regimes entirely,
[`fx_forecast.py`](src/equicast_forecasting/fx_forecast.py) accepts them as
optional parameters (only `reer_deviation` today — the rest have no
plugging-in point yet since nothing computes them) that default to `None`
and degrade to 0.0 drift (a continued random walk) when unavailable — the
math is ready for whenever a real source (FRED is the natural choice —
free, global coverage) is added in a follow-up.

One exception: `rate_diff` (the medium-horizon interest-rate-parity input)
*is* wired up to real data today, via
[`fx_rates.py`](src/equicast_forecasting/fx_rates.py) — but only for USD.
Checked live: US Treasury yields (`^IRX` 13-week, `^TNX` 10-year) resolve
cleanly via yfinance; every UK gilt/German bund/ECB-rate ticker tried
(`GB10Y=X`, `DE10Y=X`, `^BUND`, `FGBL=F`, `^GDBR10`, `EURIBOR3M=X`) 404s or
returns empty history. So `rate_diff` still resolves to `None` for any pair
that doesn't involve USD — with today's configured pairs (GBP/USD/EUR;
see `packages/fx/config/`), that's every pair currently configured, since
none of them has USD on *both* legs. The mapping is a plain dict
(`SHORT_TERM_YIELD_TICKERS`/`LONG_TERM_YIELD_TICKERS`), so adding a
currency once a reliable ticker is found is a one-line change.

### Generic vs. FX-specific

Split deliberately so the volatility/band engine can be reused by a future
stock/etf price forecast, not just FX's own interest-rate-parity/PPP model:

- **Generic** (no FX-specific knowledge at all): [`volatility.py`](src/equicast_forecasting/volatility.py)
  (GARCH/EWMA daily volatility from any chronological close-price list) and
  [`bands.py`](src/equicast_forecasting/bands.py) (the lognormal random-walk
  band construction, taking a starting price, a daily volatility, and an
  optional day-indexed drift function — reusable with a completely
  different drift model for a different asset class).
- **FX-specific**: [`fx_rates.py`](src/equicast_forecasting/fx_rates.py)
  (the yfinance yield-ticker lookups above) and
  [`fx_forecast.py`](src/equicast_forecasting/fx_forecast.py) (the
  interest-rate-parity/PPP drift schedule and top-level `fx_price_bands()`
  orchestration — currency pairs are inherently what IRP/PPP are about, so
  this part doesn't generalize the way the vol/band engine does).

### CLI

```bash
cd packages/forecasting
uv run equicast-forecasting --asset-class fx --forecast-kind price-bands --config ../fx/config/fx_pairs.dev.yaml --out ./output
uv run equicast-forecasting --asset-class fx --forecast-kind price-bands --pairs-json '[{"from":"GBP","to":"USD"}]' --out ./output
```

Writes `fx=<FROM><TO>/forecasting/price_bands.parquet` per pair — nothing
for a pair with fewer than 2 published price records. Price history is
fetched directly via `equicast-datafeed`'s `DatafeedClient.get_history`
(not `equicast-fx`'s `FXClient`) — this package deliberately depends on no
asset-class-specific package, the same reasoning `config.py`'s standalone
tickers/pairs loaders already follow for dividend forecasting.

## Stock price-band forecasting

Implements [GitHub issue #66](https://github.com/coldsofttech/equiCast/issues/66):
the same "one daily probability band per calendar day" shape as
[FX price-band forecasting](#fx-price-band-forecasting), but routed
through one of **16 sector/sub-sector schemas** (a full Morningstar-style
taxonomy — Technology; Financial Services split into Banks/Insurance/
Asset Management; Healthcare split into Pharma-Devices/Biotech;
Consumer Defensive; Consumer Cyclical; Communication Services; Utilities;
Real Estate split into REIT-equity/REIT-mortgage/Non-REIT; Energy; Basic
Materials; Industrials — see
[`sector_schemas.yaml`](src/equicast_forecasting/sector_schemas.yaml)),
each with its own named parameter set and — where equicast has the data —
its own valuation multiple driving the long-horizon reversion bias.

### Usage

```python
from equicast_forecasting import stock_price_bands

# `prices` needs at least `date`/`close` keys per record - the shape
# equicast_stock.StockClient.prices() already returns. `sector`/`industry`
# are yfinance's own `.info` values.
stock_price_bands(prices, "AAPL", "Technology", "Semiconductors", years=10)
# [{"ticker": "AAPL", "sector": "Technology", "sub_sector": "technology",
#   "date": "2026-09-10", "p10": 306.1, "p50": 312.6, "p90": 318.3,
#   "regime": "short", "volatility_model": "garch",
#   "valuation_multiple_family": "pe", "valuation_multiple": 35.8,
#   "valuation_zscore": 0.89, "revenue_cagr": 0.018,
#   "profit_margin_trend": 0.016, "rd_to_revenue": 0.083,
#   "short_interest_ratio": 0.008,
#   "last_updated": "2026-09-09T17:34:19+00:00", "source": "equicast"}, ...]
```

Raises `UnroutableSectorError` if `sector`/`industry` matches none of the
16 schemas — per the issue, "an unmapped industry should fail loudly
(raise/flag), not silently default to a generic template." Financial
Services/Healthcare/Real Estate each have sub-sector schemas only, no bare
sector-level fallback — a Financial Services stock whose industry matches
none of Banks/Insurance/Asset-Management is just as unroutable as a stock
in a sector with no schema at all.

### One Monte Carlo simulation spans the whole horizon

Unlike FX (whose short regime is a closed-form lognormal formula, see
[`bands.py`](src/equicast_forecasting/bands.py)), stock forecasting runs
**one block-bootstrap Monte Carlo simulation across the entire horizon**
(see [`monte_carlo.py`](src/equicast_forecasting/monte_carlo.py)) rather
than stitching together separately-generated model types per regime:

| Horizon | What drives it |
|---|---|
| 1w–1m ("short") | Volatility only, no directional drift — the simulated returns are rescaled to match a real GARCH(1,1)-with-EWMA-fallback estimate (same [`volatility.py`](src/equicast_forecasting/volatility.py) FX uses), so the short-horizon behavior genuinely reflects "GARCH/EWMA," not just the resampled window's own historical volatility. |
| 6m–2y ("medium") | Still no directional drift — the issue is explicit that this horizon is "Monte Carlo (bootstrapped, no valuation bias)." |
| 3y–10y ("long") | A valuation-reversion drift bias, from a real starting-multiple z-score when this sector has one wired up (see [Valuation-reversion bias](#valuation-reversion-bias)) — 0.0 otherwise. |

Resampling real historical return *blocks* (not single days independently)
preserves volatility clustering/autocorrelation a plain i.i.d. bootstrap
would lose. The trade-off against FX's approach: the short-horizon band is
sampled (Monte Carlo) rather than a closed-form formula, so expect run-to-
run sampling noise unless `seed` is fixed — a deliberate simplification
(avoids an artificial seam between differently-shaped models at the regime
boundaries), not an oversight; a large `num_paths` (2000 by default) keeps
that noise small.

### Valuation-reversion bias

The long-horizon regime's drift comes from a **starting-multiple z-score**
— literally what the issue's own notes prescribe ("Monte Carlo +
valuation-reversion bias using starting-multiple z-score") — computed by
[`fundamentals_signals.py`](src/equicast_forecasting/fundamentals_signals.py):

1. Take today's value of whichever multiple this sector's schema names
   (`valuation_multiple` in `sector_schemas.yaml` — `"pe"`, `"pe_tangible_
   book"`, `"price_to_book"`, or `"book_value"`; reused straight from
   [`equicast-metrics`](../metrics/README.md)'s own `trailing_pe`/
   `price_to_book` fields where possible, computed fresh only for
   `pe_tangible_book` — real tangible book value per share, from
   yfinance's balance sheet — which `equicast-metrics` has no field for).
2. Reconstruct that multiple's own historical series by pairing each
   available annual financial-statement period's per-share fundamental
   with the real closing price nearest that period's end date — typically
   ~4-5 points (as many years as yfinance's financials/balance sheet
   report). This is a coarse, *annual*-resolution series, not a true
   daily-resolution historical multiple — treat the resulting z-score as a
   rough "cheap/rich relative to its last few years" signal, not a
   precise statistical one.
3. Z-score today's multiple against that series' mean/stdev, then map it
   onto a daily log-return drift via `VALUATION_REVERSION_STRENGTH` (0.5)
   — an explicitly heuristic scaling coefficient (see
   [`stock_forecast.py`](src/equicast_forecasting/stock_forecast.py)'s
   `_long_drift`'s docstring), not a rigorously derived economic
   relationship.

**9 of the 16 sectors have a real multiple wired up today**: Technology,
Financial Services (all three sub-sectors), Consumer Defensive, Consumer
Cyclical, Communication Services, Utilities (approximated via price/book —
"vs asset base" in the issue's own words), Real Estate (REIT-mortgage via
book value, Non-REIT via PE), Basic Materials, and Industrials. The
remaining branches have `valuation_multiple: null` in the registry and get
0.0 long-horizon drift (a continued random walk) until real data exists:
**Healthcare (both sub-sectors)** — PEG/pipeline-based, not a
reconstructable multiple; **Real Estate — REIT (equity)** — needs FFO/AFFO,
which yfinance doesn't report at all; **Energy** — the issue's own anchor
is a commodity-cycle position, not a "vs its own history" multiple.

### Other real signals

Beyond the valuation z-score, `fundamentals_signals.compute_fundamental_
signals()` computes four more real, sector-agnostic figures the issue's
tables name directly or closely: `revenue_cagr`, `profit_margin_trend`
(a percentage-point change, not a CAGR — a margin can be negative or
near-zero, where a compound-growth ratio breaks down), `rd_to_revenue`
(`None` for the many tickers with no R&D line item), and
`short_interest_ratio` (yfinance's own `shortPercentOfFloat`). Every other
named parameter across the 16 schemas (`npl_ratio`, `fda_trial_calendar`,
`ffo_growth`, `combined_ratio_trend`, `aum_flow_trend`, ...) has no data
source anywhere in equicast today — declared in `sector_schemas.yaml` as
the target shape, not computed.

### Generic vs. stock-specific

- **Generic** (reused unchanged from FX, or newly extracted so FX and
  stock both share it): [`volatility.py`](src/equicast_forecasting/volatility.py),
  [`regimes.py`](src/equicast_forecasting/regimes.py) (the day-boundary/
  drift-taper machinery — originally part of `fx_forecast.py`, pulled out
  once stock needed the exact same math for a different drift model), and
  the new [`monte_carlo.py`](src/equicast_forecasting/monte_carlo.py)
  (asset-class-agnostic block-bootstrap engine).
- **Stock-specific**: [`sector_registry.py`](src/equicast_forecasting/sector_registry.py)/
  `sector_schemas.yaml` (the routing table),
  [`fundamentals_signals.py`](src/equicast_forecasting/fundamentals_signals.py)
  (financial-statement/short-interest signal derivation), and
  [`stock_forecast.py`](src/equicast_forecasting/stock_forecast.py) (the
  top-level orchestration).

### CLI

```bash
cd packages/forecasting
uv run equicast-forecasting --asset-class stock --forecast-kind price-bands --config ../stock/config/stocks.dev.yaml --out ./output
uv run equicast-forecasting --asset-class stock --forecast-kind price-bands --tickers-json '["AAPL"]' --out ./output --years 10 --num-paths 2000
```

Writes `stock=<TICKER>/forecasting/price_bands.parquet` per ticker —
nothing for a ticker with too little price history to forecast from.
`--forecast-kind dividends` (stock/etf) is the pre-existing dividend
forecast; `--forecast-kind price-bands` is stock/etf/fx/benchmark/future
(see [ETF](#etf-price-band-forecasting)/[Benchmark](#benchmark-price-band-forecasting)/
[Futures](#futures-price-band-forecasting) price-band forecasting below
for the etf/benchmark/future cases, added by issues #67/#68/#143). **Per
the issue's "fail loudly" requirement**, a
ticker that fails to route raises `UnroutableSectorError`, caught per-
ticker so the rest of the batch still completes and writes normally, but
`run()` re-raises a summary `ForecastBatchError` once every ticker has had
its turn — the CLI process (and, once scheduled, the CI job running it)
still exits non-zero, rather than silently reporting success with a gap.
Not yet wired into any scheduled GitHub Actions workflow — see
[docs/stock-pipeline.md](../../docs/stock-pipeline.md#forecasting).

## ETF price-band forecasting

Implements [GitHub issue #67](https://github.com/coldsofttech/equiCast/issues/67):
the same "one daily probability band per calendar day" shape as
[Stock price-band forecasting](#stock-price-band-forecasting), routed
through one of **three ETF-type schemas** (Broad/S&P, FTSE/regional,
Thematic/Focused — see
[`etf_type_schemas.yaml`](src/equicast_forecasting/etf_type_schemas.yaml))
rather than stock's 16 sector/sub-sector schemas — issue #67's own table
names a much coarser taxonomy than issue #66's.

### Usage

```python
from equicast_forecasting import etf_price_bands

# `prices` needs at least `date`/`close` keys per record - the shape
# equicast_etf.ETFClient.prices() already returns. `category` is
# yfinance's own `.info["category"]` value (a Morningstar category
# string, e.g. "Large Blend").
etf_price_bands(prices, "VOO", "Large Blend", years=10)
# [{"ticker": "VOO", "etf_type": "Broad/S&P", "etf_type_key": "broad_sp",
#   "date": "2026-09-10", "p10": 478.2, "p50": 501.6, "p90": 524.9,
#   "regime": "short", "volatility_model": "garch", "expense_ratio": 0.0003,
#   "dividend_yield": 0.013, "nav_premium_discount": 0.0001,
#   "aggregate_pe": 27.5, "last_updated": "2026-09-09T17:34:19+00:00",
#   "source": "equicast"}, ...]
```

Raises `UnroutableEtfTypeError` if `category` matches none of the 3
schemas — same "fail loudly, no generic fallback" requirement issue #66
established for stock, applied here to `category` instead of
`sector`/`industry`.

### Routing: `category` only, not two-level like stock

Unlike stock's `sector` + `industry` two-level match, an ETF routes on
yfinance's single `category` field alone (see
[`etf_type_registry.py`](src/equicast_forecasting/etf_type_registry.py)).
The category-to-type mapping was verified live against yfinance for a real
basket of ETFs (VOO/SPY/IVV/VTI/VUG/VOOG/IWM/IJH/VYM/SCHD/VIG →
Broad/S&P; VXUS/VEA/VWO/EWU/EWJ/EWZ/EWG/EWC/FXI/KWEB/INDA/VT/URTH/ACWI →
FTSE/regional; XLK/XLF/XLV/XLE/XLU/SMH/SOXX/ARKG/ICLN/GDX/JETS/VNQ/TQQQ/
SQQQ → Thematic/Focused) before writing the registry — but unlike stock's
16 exhaustively-enumerated sector/industry branches, ETF category strings
can't be exhaustively covered this way, so a genuinely novel category
still raises `UnroutableEtfTypeError` rather than guessing.

**Known limitation**: Morningstar's `category` reflects market-cap/style
characteristics, not fund *intent* — a pure style-box category (e.g. "Mid-
Cap Growth") routes to Broad/S&P even for an actively-managed thematic
fund whose real strategy is concentrated (ARKK is the clearest real
example — categorized "Mid-Cap Growth," not any sector name, even though
a human would call it thematic). No better routing signal is available
from yfinance's `.info` today.

### Same Monte Carlo engine as stock, but no valuation-reversion bias

Same regime split and same one-Monte-Carlo-simulation-spans-the-whole-
horizon approach as [stock price-band forecasting](#one-monte-carlo-simulation-spans-the-whole-horizon)
(short: GARCH/EWMA-calibrated volatility, no drift; medium: bootstrap, no
bias; long: bootstrap + a bias) — but the long-horizon bias isn't a
valuation-reversion z-score. That needs a reconstructable *historical*
multiple series (see
[fundamentals_signals.py](src/equicast_forecasting/fundamentals_signals.py)),
which funds can't supply — ETFs file no annual financial statements the
way stocks do, so there's no way to build the coarse annual-resolution
series stock's own z-score relies on. So **no ETF type gets a
valuation-reversion bias**, unlike stock's 9-of-16 sectors.

What every ETF genuinely does have instead is its own real **expense
ratio** — a known, structural drag on total return, not a speculative
signal. `etf_forecast.py`'s `_long_drift` turns that into a constant daily
log-return drag (`-expense_ratio / DAYS_PER_YEAR`), active for as long as
the long regime's drift schedule keeps it tapered in. Unlike stock's own
`_long_drift` (which spreads a one-time valuation gap evenly over the
years *remaining* — a multiple reverting toward its mean is a one-shot
adjustment), this doesn't scale by a reversion window: a fee doesn't
"revert," it just keeps applying at the same rate.

### Real signals computed today

Of issue #67's named per-type/cross-cutting fields, only four have a real
data source in equicast today (see
[`etf_signals.py`](src/equicast_forecasting/etf_signals.py)) — the same
"declare the target shape, compute what's real, leave the rest null"
approach `etf_type_schemas.yaml`/`sector_schemas.yaml` both take:

- **`expense_ratio`** (cross-cutting) — real, `.info`'s `netExpenseRatio`,
  the same field `equicast_etf.client.ETFClient.profile()` already
  surfaces. Also what drives the long-horizon bias above.
- **`dividend_yield`** (named directly under FTSE/regional's long
  horizon) — real, `.info`'s own `yield` (trailing distribution yield).
- **`nav_premium_discount`** (cross-cutting) — real, `(market_price -
  nav) / nav` from `.info`'s `navPrice` vs current price — the one
  genuinely ETF-specific *computed* signal (a stock has no separate NAV
  to compare against).
- **`aggregate_pe`** (the real-data half of Broad/S&P's `agg_forward_
  pe_vs_history` / `starting_agg_pe_cape_adj`) — reuses
  `equicast_metrics.fundamentals.compute_fundamentals`'s own
  `trailing_pe` resolution unchanged: yfinance reports a look-through
  aggregate P/E for many broad-market ETFs in the same `.info["trailingPE"]`
  field a stock uses. Per the issue's own note, treat this as
  lower-confidence/lower-availability than a single-stock trailing P/E —
  and, per the point above, there's no historical series to z-score it
  against, so it's reported as a snapshot only, with no valuation-tilt
  effect on the bands themselves.

Every other named field (`options_skew`, `iv_vix_proxy`, `top5_holding_
weight`, `sector_weight_drift`, `tracking_error`, `theme_durability_risk`,
`concentration_ratio_top10`, ...) needs options-market, per-holding, or
benchmark-tracking data no equicast pipeline ingests today — declared in
`etf_type_schemas.yaml` as the target shape, not computed.

### CLI

```bash
cd packages/forecasting
uv run equicast-forecasting --asset-class etf --forecast-kind price-bands --config ../etf/config/etfs.dev.yaml --out ./output
uv run equicast-forecasting --asset-class etf --forecast-kind price-bands --tickers-json '["VOO"]' --out ./output --years 10 --num-paths 2000
```

Writes `etf=<TICKER>/forecasting/price_bands.parquet` per ticker —
nothing for a ticker with too little price history to forecast from.
Same "fail loudly" `UnroutableEtfTypeError`/`ForecastBatchError` handling
as stock's own CLI wiring above. Not yet wired into any scheduled GitHub
Actions workflow — see
[docs/etf-pipeline.md](../../docs/etf-pipeline.md#forecasting).

## Benchmark price-band forecasting

Implements [GitHub issue #68](https://github.com/coldsofttech/equiCast/issues/68):
the same "one daily probability band per calendar day" shape as
[Stock](#stock-price-band-forecasting)/[ETF](#etf-price-band-forecasting)
price-band forecasting, applied at the index level. Routed through a
**per-index schema** keyed directly off `equicast_benchmark`'s own S3
partition key (e.g. `"SP500"`, `"FTSE100"`) — see
[`benchmark_schemas.yaml`](src/equicast_forecasting/benchmark_schemas.yaml)
— rather than any substring/taxonomy match against a fetched field: a
benchmark's own config already names it exactly, there's nothing to infer.

### Usage

```python
from equicast_forecasting import benchmark_price_bands

# `prices` needs at least `date`/`close` keys per record - the shape
# equicast_benchmark.BenchmarkClient.prices() already returns.
benchmark_price_bands(prices, "SP500", years=10)
# [{"key": "SP500", "benchmark": "S&P 500", "currency_sensitivity": "low",
#   "date": "2026-09-10", "p10": 4312.5, "p50": 4501.2, "p90": 4689.8,
#   "regime": "short", "volatility_model": "garch", "cape_zscore": None,
#   "last_updated": "2026-09-09T17:34:19+00:00", "source": "equicast"}, ...]
```

Raises `UnroutableBenchmarkError` if `key` matches no registered
benchmark — same "fail loudly, no generic fallback" requirement issues
#66/#67 already established, applied here too: **every benchmark
configured in [`packages/benchmark/config/`](../benchmark/config/) needs
its own explicit schema entry** — unlike ETF's 3-type "Other" catch-all,
there's no shared fallback bucket here (a deliberate choice: the issue's
own table has an "Other" row, but this registry instead gives every one
of today's 15 configured benchmarks — including the ones the issue's
table would call "Other," like DAX/Nikkei 225 — its own bespoke entry).

### Same Monte Carlo engine as stock/ETF, but no real bias anywhere

Same regime split as stock/ETF (short: GARCH/EWMA-calibrated volatility,
no drift; medium: bootstrap, no bias; long: bootstrap + a valuation-
reversion bias, same z-score-reverts-toward-its-mean formula
`stock_forecast.py`'s own `_long_drift` uses) — but **no benchmark gets a
real bias today**. Unlike stock (a real per-sector multiple z-score for
9/16 sectors) or ETF (a real expense-ratio drag for every fund), a raw
index ticker reports no fundamentals at all: verified live against
yfinance's `.info` for `^GSPC`/`^FTSE`/`^RUA`/`^N225`/`^GDAXI`/`^DJI`/
`^NDX`, every one returns `None` for `trailingPE`/`dividendYield`/
`priceToBook`/`category`. There's no single issuer to report a P/E or
CAPE for the way a stock or an ETF has.

`benchmark_price_bands()`'s `cape_zscore` parameter is kept real and
explicit (defaulting to `None`, degrading the long horizon to a plain
unbiased bootstrap) rather than inlined as a hardcoded constant — exactly
how FX forecasting's own `reer_deviation` (also always `None` today) is
wired — so a future real CAPE/aggregate-PE data source only needs to pass
a value in, not change this module's shape.

### `currency_sensitivity`: a real per-index config value, not a constant

The issue is explicit: "don't reuse the same `currency_drag_benefit`
weighting across all benchmarks; make it a configurable per-index
parameter, not a constant." Each schema entry declares its own
`currency_sensitivity` (`none`/`low`/`moderate`/`high`) — FTSE 100 is
`high` (the issue's own framing: its heavy overseas-earnings weighting
means FX correlation "matters more here than for S&P 500/Russell 3000",
both `low`) — returned on every record as real per-index *configuration*.
There's no real historical FX-correlation signal behind it yet to turn
into an actual drift number, though — same honest "the config knob
exists, the number is 0.0 until real data arrives" shape `cape_zscore`
has. The classification itself is illustrative (ordinary market knowledge
— e.g. MSCI Emerging Markets classified `high` for real EM currency
volatility — not derived from any real data equicast ingests); see
`benchmark_schemas.yaml`'s own header comment for the full reasoning per
benchmark.

### CLI

```bash
cd packages/forecasting
uv run equicast-forecasting --asset-class benchmark --forecast-kind price-bands --config ../benchmark/config/benchmarks.dev.yaml --out ./output
uv run equicast-forecasting --asset-class benchmark --forecast-kind price-bands --benchmarks-json '[{"key":"SP500","symbol":"^GSPC"}]' --out ./output --years 10 --num-paths 2000
```

Writes `benchmark=<KEY>/forecasting/price_bands.parquet` per benchmark —
nothing for a benchmark with too little price history to forecast from.
Same "fail loudly" `UnroutableBenchmarkError`/`ForecastBatchError`
handling as stock's/ETF's own CLI wiring above. Not yet wired into any
scheduled GitHub Actions workflow — see
[docs/benchmark-pipeline.md](../../docs/benchmark-pipeline.md#forecasting).

## Futures price-band forecasting

Implements [GitHub issue #143](https://github.com/coldsofttech/equiCast/issues/143):
the same "one daily probability band per calendar day" shape as
[Stock](#stock-price-band-forecasting)/[ETF](#etf-price-band-forecasting)/
[Benchmark](#benchmark-price-band-forecasting) price-band forecasting,
applied to futures contracts. Routed through one of **5 commodity-class
schemas** (Precious Metals, Energy, Industrial Metals, Grains, Softs — see
[`commodity_class_schemas.yaml`](src/equicast_forecasting/commodity_class_schemas.yaml)),
each declaring an explicit list of the futures (by their
`equicast_future` S3 partition key, e.g. `"GOLD"`) that belong to it,
matching the issue's own table exactly.

### Usage

```python
from equicast_forecasting import future_price_bands

# `prices` needs at least `date`/`close` keys per record - the shape
# equicast_future.FutureClient.prices() already returns.
future_price_bands(prices, "GOLD", years=10)
# [{"key": "GOLD", "commodity_class": "Precious Metals",
#   "date": "2026-09-10", "p10": 2180.4, "p50": 2312.6, "p90": 2448.9,
#   "regime": "short", "volatility_model": "garch",
#   "basis_vs_cost_of_carry": None,
#   "last_updated": "2026-09-09T17:34:19+00:00", "source": "equicast"}, ...]
```

Raises `UnroutableCommodityError` if `key` matches none of the 5 classes'
`symbols` lists — same "fail loudly, no generic fallback" requirement
issues #66/#67/#68 already established: **every future configured in
[`packages/future/config/`](../future/config/) needs its own explicit
class membership** — there's no shared fallback bucket, same choice
benchmark forecasting made over ETF's "Other" catch-all.

### Its own schema branch, not stock/ETF with nulled-out fields

Per the issue: "Futures don't have PE/EPS/FFO — no earnings, no balance
sheet. Forecasting here is driven by supply/demand fundamentals, curve
structure (contango/backwardation), and storage/carry economics, not
valuation multiples. Schema needs to be its own branch, not a reuse of
the stock/ETF schema with nulled-out fields." Every parameter name in
`commodity_class_schemas.yaml` (`cot_positioning`, `opec_meeting_calendar`,
`stocks_to_use_ratio`, `curve_structure`, ...) is lifted verbatim from the
issue's own table and shares no field names with `sector_schemas.yaml`/
`etf_type_schemas.yaml`/`benchmark_schemas.yaml`.

### Same Monte Carlo engine as stock/ETF/benchmark, but its own reversion anchor

Same regime split (short: GARCH/EWMA-calibrated volatility, no drift;
medium: bootstrap, no bias; long: bootstrap + a reversion bias) — but per
the issue's own explicit instruction, the long-horizon anchor is **not** a
valuation multiple: "the long-horizon reversion target is curve-implied
fair value / cost-of-carry... the schema needs its own reversion-anchor
field (e.g. `basis_vs_cost_of_carry`)." `future_forecast.py`'s
`_long_drift` uses exactly that field — the same z-score-reverts-toward-
its-mean formula shape stock's/benchmark's own `_long_drift` use, just
anchored to a curve-implied fair-value gap instead of a valuation
multiple's historical average.

**No future gets a real bias today.** Per the issue's own explicitly-
flagged data gap: "USDA WASDE, EIA inventory, and CFTC COT reports are
not available via yfinance — yfinance gives OHLC futures price history
only. This issue should ship with those fields defaulting to
None/unavailable... with a follow-up issue for wiring real data
sources." The same is true of the spot-price/storage/financing-cost data
a real cost-of-carry fair value would need — `equicast_future.
FutureClient.profile()` mirrors `BenchmarkClient`'s shape exactly, no
fundamentals field at all. `basis_vs_cost_of_carry` is kept as a real,
explicit parameter (defaulting to `None`, degrading the long horizon to a
plain unbiased bootstrap) rather than inlined as a hardcoded constant —
exactly how FX forecasting's own `reer_deviation` (also always `None`
today) is wired.

### Continuous-contract-construction caveat (verified, not resolved)

Per the issue's own instruction — "Continuous contract construction...
should be verified/documented before backtesting — an unadjusted roll can
inject artificial jumps that corrupt the GARCH fit and the historical
bootstrap sample alike" — this was checked live before shipping: 2-year
daily return distributions for `GC=F`/`CL=F`/`NG=F`. Gold is comparatively
clean (4 of 504 trading days moved >5%); WTI crude had 35 such days;
natural gas had 97 (~19% of trading days), with a single-day move as large
as 47%. The jump dates don't cluster on a fixed day-of-month across
contracts the way a purely mechanical, un-back-adjusted monthly roll would
— more consistent with genuine commodity event-driven volatility (natural
gas is a famously volatile market) than a systematic roll artifact, but
yfinance doesn't publicly document its `"=F"` continuous-contract
construction methodology (back-adjusted vs. raw-spliced), so this can't be
fully ruled out. **Flagged here, unresolved** — the GARCH/EWMA volatility
estimate and Monte Carlo bootstrap both use this same price history as-is,
so if roll jumps ever turn out to be a real, still-present contributor,
they're currently feeding directly into both.

### CLI

```bash
cd packages/forecasting
uv run equicast-forecasting --asset-class future --forecast-kind price-bands --config ../future/config/futures.dev.yaml --out ./output
uv run equicast-forecasting --asset-class future --forecast-kind price-bands --futures-json '[{"key":"GOLD","symbol":"GC=F"}]' --out ./output --years 10 --num-paths 2000
```

Writes `future=<KEY>/forecasting/price_bands.parquet` per future —
nothing for a future with too little price history to forecast from. Same
"fail loudly" `UnroutableCommodityError`/`ForecastBatchError` handling as
stock's/ETF's/benchmark's own CLI wiring above. Not yet wired into any
scheduled GitHub Actions workflow — see
[docs/future-pipeline.md](../../docs/future-pipeline.md#forecasting).

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
