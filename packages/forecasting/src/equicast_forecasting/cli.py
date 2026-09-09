"""CLI: forecast future dividend payouts (stock/etf) or daily FX price
probability bands (fx) for every configured ticker/pair.

Dividend forecasting: for each ticker, fetches its full dividend history
via `DividendsClient`, projects it forward with `equicast_forecasting.
dividends()`, and writes `<asset_class>=<TICKER>/forecasting/
dividends.parquet` — nothing at all for a ticker with no dependable cadence
to forecast (an "irregular"/"not_applicable" payer).

FX price-band forecasting: for each pair, fetches its full price history
directly via `DatafeedClient.get_history` (not `equicast-fx`'s `FXClient` —
this package deliberately doesn't depend on any asset-class-specific
package, same reasoning `config.py`'s docstring gives for its own
standalone config loaders), projects it forward with `equicast_forecasting.
fx_forecast.fx_price_bands()`, and writes `fx=<FROM><TO>/forecasting/
price_bands.parquet`.

Either way, each ticker's/pair's fetch-and-forecast is an independent task
submitted to the same worker pool, so they run concurrently rather than one
after the other.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path

from equicast_datafeed import DatafeedClient
from equicast_dividends import DividendsClient

from equicast_forecasting.config import (
    FxPairRef,
    load_fx_pairs,
    load_tickers,
    parse_fx_pairs_json,
    parse_tickers_json,
)
from equicast_forecasting.forecast import dividends
from equicast_forecasting.fx_forecast import fx_price_bands
from equicast_forecasting.writer import (
    write_dividend_forecast_parquet,
    write_fx_price_bands_parquet,
)

logger = logging.getLogger(__name__)

#: Full-history period passed to `DatafeedClient.get_history` when fetching
#: an FX pair's price series to forecast from — as much real volatility
#: history as yfinance has, not just the current year, since a longer
#: series makes for a materially more reliable GARCH(1,1) fit (see
#: volatility.py's `GARCH_MIN_OBSERVATIONS`).
FX_HISTORY_PERIOD = "max"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Forecast each configured ticker's future dividend payouts (stock/etf) or "
        "each configured pair's daily FX price probability bands (fx), writing one Parquet "
        "file per ticker/pair."
    )
    parser.add_argument(
        "--asset-class",
        required=True,
        choices=["stock", "etf", "fx"],
        help="Determines both the forecast kind (dividends for stock/etf, price bands for fx) "
        "and the S3 key prefix written to.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--config",
        type=Path,
        help="Path to a tickers YAML config (stock/etf) or an FX pairs YAML config (fx).",
    )
    source.add_argument(
        "--tickers-json",
        help="JSON array of ticker strings (stock/etf only; e.g. one matrix chunk).",
    )
    source.add_argument(
        "--pairs-json",
        help='JSON array of {"from": ..., "to": ...} objects (fx only; e.g. one matrix chunk).',
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for Parquet files."
    )
    parser.add_argument(
        "--years",
        type=int,
        default=10,
        help="Forecast horizon in years (default: 10).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Ticker/pair fetch-and-forecast tasks run concurrently, up to this many at once "
        "(default: 1).",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=1,
        help="Max yfinance calls allowed per --period-seconds, shared across all workers.",
    )
    parser.add_argument(
        "--period-seconds",
        type=float,
        default=1.0,
        help="Rate-limit window, in seconds (default: 1.0).",
    )
    return parser


def _validate_source_for_asset_class(
    asset_class: str, tickers_json: str | None, pairs_json: str | None
) -> None:
    if asset_class == "fx" and tickers_json is not None:
        raise ValueError("--tickers-json is stock/etf only; use --pairs-json (or --config) for fx.")
    if asset_class != "fx" and pairs_json is not None:
        raise ValueError("--pairs-json is fx only; use --tickers-json (or --config) for stock/etf.")


def _load_tickers(config: Path | None, tickers_json: str | None) -> list[str]:
    if tickers_json is not None:
        return parse_tickers_json(tickers_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_tickers(config)


def _load_fx_pairs(config: Path | None, pairs_json: str | None) -> list[FxPairRef]:
    if pairs_json is not None:
        return parse_fx_pairs_json(pairs_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_fx_pairs(config)


def _forecast_task(
    ticker: str, datafeed: DatafeedClient, output_dir: Path, asset_class: str, years: int
) -> Path | None:
    logger.info("Forecasting dividends for %s", ticker)
    dividends_client = DividendsClient(ticker, datafeed=datafeed)
    history = dividends_client.dividends(full_load=True)
    forecast = dividends(history, years=years)
    return write_dividend_forecast_parquet(forecast, output_dir, asset_class)


def _fx_price_records(datafeed: DatafeedClient, symbol: str) -> list[dict[str, float | str]]:
    """The minimal `{date, close}` records `fx_price_bands()` needs, read
    straight off `DatafeedClient.get_history` — no `equicast-fx` dependency
    (see this module's own docstring for why)."""
    history = datafeed.get_history(symbol, period=FX_HISTORY_PERIOD)
    return [
        {"date": index.date().isoformat(), "close": float(row["Close"])}
        for index, row in history.iterrows()
    ]


def _fx_forecast_task(
    pair: FxPairRef, datafeed: DatafeedClient, output_dir: Path, years: int
) -> Path | None:
    logger.info("Forecasting FX price bands for %s%s", pair.from_currency, pair.to_currency)
    symbol = f"{pair.from_currency}{pair.to_currency}=X"
    prices = _fx_price_records(datafeed, symbol)
    forecast = fx_price_bands(
        prices, pair.from_currency, pair.to_currency, datafeed=datafeed, years=years
    )
    return write_fx_price_bands_parquet(forecast, output_dir)


def run(
    asset_class: str,
    config: Path | None,
    output_dir: Path,
    tickers_json: str | None = None,
    pairs_json: str | None = None,
    years: int = 10,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> list[Path]:
    _validate_source_for_asset_class(asset_class, tickers_json, pairs_json)

    # One DatafeedClient (and its rate limiter) shared across every worker, so
    # the configured request rate is a real ceiling regardless of concurrency.
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)

    tasks: list[Callable[[], Path | None]]
    if asset_class == "fx":
        pairs = _load_fx_pairs(config, pairs_json)
        tasks = [partial(_fx_forecast_task, pair, datafeed, output_dir, years) for pair in pairs]
    else:
        tickers = _load_tickers(config, tickers_json)
        tasks = [
            partial(_forecast_task, ticker, datafeed, output_dir, asset_class, years)
            for ticker in tickers
        ]

    written: list[Path] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task) for task in tasks]
        for future in as_completed(futures):
            path = future.result()
            if path is not None:
                written.append(path)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    for path in run(
        args.asset_class,
        args.config,
        args.out,
        tickers_json=args.tickers_json,
        pairs_json=args.pairs_json,
        years=args.years,
        max_workers=args.max_workers,
        max_calls=args.max_calls,
        period_seconds=args.period_seconds,
    ):
        print(path)


if __name__ == "__main__":
    main()
