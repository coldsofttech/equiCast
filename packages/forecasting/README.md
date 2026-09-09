# equicast-forecasting

Projects a symbol's future dividend payouts from its actual dividend
history, built on [equicast-dividends](../dividends/README.md), and (see
[FX price-band forecasting](#fx-price-band-forecasting) below) daily FX
price probability bands from actual price history plus whatever real
interest-rate data is available.

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
uv run equicast-forecasting --asset-class fx --config ../fx/config/fx_pairs.dev.yaml --out ./output
uv run equicast-forecasting --asset-class fx --pairs-json '[{"from":"GBP","to":"USD"}]' --out ./output
```

Writes `fx=<FROM><TO>/forecasting/price_bands.parquet` per pair — nothing
for a pair with fewer than 2 published price records. Price history is
fetched directly via `equicast-datafeed`'s `DatafeedClient.get_history`
(not `equicast-fx`'s `FXClient`) — this package deliberately depends on no
asset-class-specific package, the same reasoning `config.py`'s standalone
tickers/pairs loaders already follow for dividend forecasting.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run mypy src/
```
