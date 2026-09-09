# equicast-forecasting

Projects a symbol's future dividend payouts from its actual dividend
history, built on [equicast-dividends](../dividends/README.md); daily FX
price probability bands from actual price history plus whatever real
interest-rate data is available (see
[FX price-band forecasting](#fx-price-band-forecasting)); and daily,
sector-routed stock price probability bands from actual price/fundamentals
data (see [Stock price-band forecasting](#stock-price-band-forecasting)).

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
forecast; `--forecast-kind price-bands` is fx/stock only (not etf — issue
#66 is stock-specific). **Per the issue's "fail loudly" requirement**, a
ticker that fails to route raises `UnroutableSectorError`, caught per-
ticker so the rest of the batch still completes and writes normally, but
`run()` re-raises a summary `ForecastBatchError` once every ticker has had
its turn — the CLI process (and, once scheduled, the CI job running it)
still exits non-zero, rather than silently reporting success with a gap.
Not yet wired into any scheduled GitHub Actions workflow — see
[docs/stock-pipeline.md](../../docs/stock-pipeline.md#forecasting).

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
