"""ETF-specific real signal derivation - feeds etf_forecast.py's output
fields and its expense-ratio-drag long-horizon bias (see that module's
docstring for why expense ratio, not a valuation z-score, drives ETF
forecasting's long-horizon regime).

Genuinely ETF-specific (fund `.info` fields with no stock equivalent -
expense ratio, NAV, distribution yield), unlike volatility.py/bands.py/
monte_carlo.py/regimes.py, which stock_forecast.py and this module both
reuse unchanged.

Of GitHub issue #67's named per-type/cross-cutting fields, only four have
a real data source in equicast today - the same "declare the target shape,
compute what's real, leave the rest null" approach sector_schemas.yaml/
fundamentals_signals.py already established for stock:

- `expense_ratio` (cross-cutting) - real, `netExpenseRatio` off `.info`,
  the same field `equicast_etf.client.ETFClient.profile()` already surfaces.
- `dividend_yield` (named directly under FTSE/regional's long horizon) -
  real, `.info`'s own `yield` (trailing distribution yield), same field
  `ETFClient.profile()` already surfaces.
- `nav_premium_discount` (cross-cutting) - real, computed here from
  `.info`'s `navPrice` vs current market price - the one genuinely
  ETF-specific *computed* signal (a stock has no separate NAV to compare
  against).
- `aggregate_pe` (the real-data half of Broad/S&P's `agg_forward_pe_vs_
  history` / `starting_agg_pe_cape_adj`) - reuses `equicast_metrics.
  fundamentals.compute_fundamentals`'s own `trailing_pe` resolution
  unchanged: yfinance reports a look-through aggregate P/E for many
  broad-market ETFs in the same `.info["trailingPE"]` field a stock uses,
  and `compute_fundamentals` already prefers that over any statement-based
  fallback (which degrades to `None` anyway - ETFs file no financial
  statements, so every statement-row lookup empty-returns). Per the
  issue's own note, treat this as lower-confidence/lower-availability than
  a single-stock trailing P/E.

Every other named field (`options_skew`, `iv_vix_proxy`, `top5_holding_
weight`, `sector_weight_drift`, `tracking_error`, `theme_durability_risk`,
...) needs options-market, per-holding, or benchmark-tracking data no
equicast pipeline ingests today - declared in etf_type_schemas.yaml as the
target shape, not computed here. In particular, there's no real
*historical* aggregate-P/E series to z-score `aggregate_pe` against the
way stock_forecast.py z-scores a sector's own multiple (that needs annual
financial-statement history, which funds don't file) - so unlike stock's
9-of-16 sectors, no ETF type gets a valuation-reversion bias; see
etf_forecast.py's module docstring for what drives the long horizon
instead.
"""

from __future__ import annotations

from typing import Any

from equicast_datafeed import DatafeedClient
from equicast_metrics.fundamentals import compute_fundamentals


def expense_ratio(info: dict[str, Any]) -> float | None:
    """Annual expense ratio as a fraction (e.g. `0.03` for VOO's real
    0.03%... i.e. `0.0003` - yfinance's `netExpenseRatio` is already a
    fraction, not a percentage) - `None` if yfinance doesn't report it."""
    value = info.get("netExpenseRatio")
    return float(value) if value is not None else None


def dividend_yield(info: dict[str, Any]) -> float | None:
    """Trailing distribution yield as a fraction - `None` if yfinance
    doesn't report it."""
    value = info.get("yield")
    return float(value) if value is not None else None


def nav_premium_discount(info: dict[str, Any]) -> float | None:
    """`(market_price - nav) / nav` - positive when the ETF trades at a
    premium to its net asset value, negative at a discount. `None` if
    either `navPrice` or a current market price is missing, or `navPrice`
    is `0` (would divide by zero)."""
    nav = info.get("navPrice")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if nav is None or price is None or nav == 0:
        return None
    return (price - nav) / nav


def aggregate_pe(info: dict[str, Any]) -> float | None:
    """The fund's look-through aggregate trailing P/E, when yfinance
    reports one for this ETF (see module docstring) - `None` otherwise.
    ETFs file no financial statements, so `compute_fundamentals`'s
    statement-based fallbacks always empty-return for one; passing `lambda:
    None` for both avoids two wasted fetches that would just return empty
    frames anyway."""
    fundamentals, _ = compute_fundamentals(info, lambda: None, lambda: None)
    return fundamentals["trailing_pe"]


def compute_etf_signals(datafeed: DatafeedClient, symbol: str) -> dict[str, float | None]:
    """The real signals equicast can compute today for `symbol` - see
    module docstring for which of issue #67's named fields each maps to."""
    info = datafeed.get_info(symbol)
    return {
        "expense_ratio": expense_ratio(info),
        "dividend_yield": dividend_yield(info),
        "nav_premium_discount": nav_premium_discount(info),
        "aggregate_pe": aggregate_pe(info),
    }
