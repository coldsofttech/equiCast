"""CLI: forecast future dividend payouts (stock/etf), daily FX price
probability bands (fx), or daily sector-routed stock/ETF/benchmark/future
price probability bands (stock/etf/benchmark/future) for every configured
ticker/pair/benchmark/future.

`--forecast-kind` selects which model runs, since "stock" can mean either
kind of forecast:

Dividend forecasting (`--forecast-kind dividends`, stock/etf only): for
each ticker, fetches its full dividend history via `DividendsClient`,
projects it forward with `equicast_forecasting.dividends()`, and writes
`<asset_class>=<TICKER>/forecasting/dividends.parquet` — nothing at all
for a ticker with no dependable cadence to forecast (an "irregular"/
"not_applicable" payer).

FX price-band forecasting (`--forecast-kind price-bands`, fx only): for
each pair, fetches its full price history directly via `DatafeedClient.
get_history` (not `equicast-fx`'s `FXClient` — this package deliberately
doesn't depend on any asset-class-specific package, same reasoning
`config.py`'s docstring gives for its own standalone config loaders),
projects it forward with `equicast_forecasting.fx_forecast.
fx_price_bands()`, and writes `fx=<FROM><TO>/forecasting/
price_bands.parquet`.

Stock price-band forecasting (`--forecast-kind price-bands`, stock only,
GitHub issue #66): for each ticker, fetches its full price history plus
`sector`/`industry` (again straight off `DatafeedClient`, not
`equicast-stock`), routes it to one of 16 sector/sub-sector schemas (see
sector_registry.py) and projects it forward with `equicast_forecasting.
stock_forecast.stock_price_bands()`, writing `stock=<TICKER>/forecasting/
price_bands.parquet`. Per the issue, an unroutable sector/industry "fails
loudly" — `_stock_forecast_task` logs and skips just that ticker (so one
unmapped stock doesn't abort every other ticker in the batch), but `run()`
re-raises a summary `ForecastBatchError` once every ticker has had its
turn, so the overall CLI invocation (and, once scheduled, the GitHub
Actions job running it) still exits non-zero and fails visibly — the
already-forecasted tickers' Parquet files are still written either way.

ETF price-band forecasting (`--forecast-kind price-bands`, etf only,
GitHub issue #67): the same shape as stock's, but routes each ticker's
`category` (again straight off `DatafeedClient`) to one of three ETF-type
schemas (see etf_type_registry.py) and projects it forward with
`equicast_forecasting.etf_forecast.etf_price_bands()`, writing
`etf=<TICKER>/forecasting/price_bands.parquet`. An unroutable category
"fails loudly" the same way an unroutable stock sector/industry does —
`_etf_forecast_task` logs and skips just that ticker, contributing to the
same `ForecastBatchError` summary `run()` re-raises once the batch
completes (shared across stock/etf/benchmark/future routing failures when
more than one happen to run in the same invocation, though in practice
each runs as its own separate `--asset-class` invocation).

Benchmark (market index) price-band forecasting (`--forecast-kind
price-bands`, benchmark only, GitHub issue #68): for each configured
benchmark, fetches its full price history straight off `DatafeedClient`
(the benchmark's own `key`/`symbol` come from config, same shape
`equicast-benchmark`'s own config uses — see config.py's `BenchmarkRef`),
routes `key` to one of its per-index schemas (see benchmark_registry.py —
**no generic fallback**, every configured benchmark needs its own
explicit schema entry) and projects it forward with `equicast_forecasting.
benchmark_forecast.benchmark_price_bands()`, writing
`benchmark=<KEY>/forecasting/price_bands.parquet`. An unroutable key
"fails loudly" the same way an unroutable stock sector/industry or ETF
category does — `_benchmark_forecast_task` logs and skips just that
benchmark, contributing to the same `ForecastBatchError` summary.

Futures price-band forecasting (`--forecast-kind price-bands`, future
only, GitHub issue #143): for each configured future, fetches its full
price history straight off `DatafeedClient` (the future's own `key`/
`symbol` come from config, same shape `equicast-future`'s own config
uses — see config.py's `FutureRef`), routes `key` to one of 5 commodity-
class schemas (see commodity_registry.py — **no generic fallback**, every
configured future needs its own explicit class membership) and projects
it forward with `equicast_forecasting.future_forecast.
future_price_bands()`, writing `future=<KEY>/forecasting/
price_bands.parquet`. An unroutable key "fails loudly" the same way an
unroutable stock sector/industry, ETF category, or benchmark key does —
`_future_forecast_task` logs and skips just that future, contributing to
the same `ForecastBatchError` summary.

Either way, each ticker's/pair's/benchmark's/future's fetch-and-forecast
is an independent task submitted to the same worker pool, so they run
concurrently rather than one after the other.
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

from equicast_forecasting.benchmark_forecast import benchmark_price_bands
from equicast_forecasting.benchmark_registry import UnroutableBenchmarkError
from equicast_forecasting.commodity_registry import UnroutableCommodityError
from equicast_forecasting.config import (
    BenchmarkRef,
    FutureRef,
    FxPairRef,
    load_benchmarks,
    load_futures,
    load_fx_pairs,
    load_tickers,
    parse_benchmarks_json,
    parse_futures_json,
    parse_fx_pairs_json,
    parse_tickers_json,
)
from equicast_forecasting.etf_forecast import etf_price_bands
from equicast_forecasting.etf_type_registry import UnroutableEtfTypeError
from equicast_forecasting.forecast import dividends
from equicast_forecasting.future_forecast import future_price_bands
from equicast_forecasting.fx_forecast import fx_price_bands
from equicast_forecasting.monte_carlo import DEFAULT_NUM_PATHS
from equicast_forecasting.sector_registry import UnroutableSectorError
from equicast_forecasting.stock_forecast import stock_price_bands
from equicast_forecasting.writer import (
    write_benchmark_price_bands_parquet,
    write_dividend_forecast_parquet,
    write_etf_price_bands_parquet,
    write_future_price_bands_parquet,
    write_fx_price_bands_parquet,
    write_stock_price_bands_parquet,
)

logger = logging.getLogger(__name__)

#: Full-history period passed to `DatafeedClient.get_history` when fetching
#: an FX pair's or stock's price series to forecast from — as much real
#: volatility history as yfinance has, not just the current year, since a
#: longer series makes for a materially more reliable GARCH(1,1) fit (see
#: volatility.py's `GARCH_MIN_OBSERVATIONS`) and Monte Carlo bootstrap.
FULL_HISTORY_PERIOD = "max"


class ForecastBatchError(RuntimeError):
    """Raised by `run()` when one or more tickers/benchmarks/futures
    failed to route to a stock, ETF, benchmark, or future forecasting
    schema (see sector_registry.UnroutableSectorError / etf_type_registry.
    UnroutableEtfTypeError / benchmark_registry.UnroutableBenchmarkError /
    commodity_registry.UnroutableCommodityError) — every other ticker/
    benchmark/future in the batch still ran and had its Parquet written;
    this only ensures the overall CLI invocation still exits non-zero, per
    issue #66/#67/#68/#143's "fail loudly" requirement, rather than
    silently reporting success."""


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Forecast each configured ticker's future dividend payouts (stock/etf) or "
        "each configured ticker's/pair's/benchmark's/future's daily price probability bands "
        "(stock/etf/fx/benchmark/future), writing one Parquet file per ticker/pair/"
        "benchmark/future."
    )
    parser.add_argument(
        "--asset-class",
        required=True,
        choices=["stock", "etf", "fx", "benchmark", "future"],
        help="Determines both which tickers/pairs/benchmarks/futures this can run against and "
        "the S3 key prefix written to.",
    )
    parser.add_argument(
        "--forecast-kind",
        required=True,
        choices=["dividends", "price-bands"],
        help='"dividends" is stock/etf only; "price-bands" is stock/etf/fx/benchmark/future.',
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--config",
        type=Path,
        help="Path to a tickers YAML config (stock/etf), an FX pairs YAML config (fx), a "
        "benchmarks YAML config (benchmark), or a futures YAML config (future).",
    )
    source.add_argument(
        "--tickers-json",
        help="JSON array of ticker strings (stock/etf only; e.g. one matrix chunk).",
    )
    source.add_argument(
        "--pairs-json",
        help='JSON array of {"from": ..., "to": ...} objects (fx only; e.g. one matrix chunk).',
    )
    source.add_argument(
        "--benchmarks-json",
        help='JSON array of {"key": ..., "symbol": ...} objects (benchmark only; e.g. one '
        "matrix chunk).",
    )
    source.add_argument(
        "--futures-json",
        help='JSON array of {"key": ..., "symbol": ...} objects (future only; e.g. one '
        "matrix chunk).",
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
        "--num-paths",
        type=int,
        default=DEFAULT_NUM_PATHS,
        help="Monte Carlo simulated paths per stock forecast (default: "
        f"{DEFAULT_NUM_PATHS}). Ignored for dividends/fx forecasting.",
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
    asset_class: str,
    tickers_json: str | None,
    pairs_json: str | None,
    benchmarks_json: str | None,
    futures_json: str | None,
) -> None:
    if asset_class not in ("stock", "etf") and tickers_json is not None:
        raise ValueError(
            "--tickers-json is stock/etf only; use the right source flag (or --config)."
        )
    if asset_class != "fx" and pairs_json is not None:
        raise ValueError("--pairs-json is fx only; use the right source flag (or --config).")
    if asset_class != "benchmark" and benchmarks_json is not None:
        raise ValueError(
            "--benchmarks-json is benchmark only; use the right source flag (or --config)."
        )
    if asset_class != "future" and futures_json is not None:
        raise ValueError(
            "--futures-json is future only; use the right source flag (or --config)."
        )


def _validate_forecast_kind(asset_class: str, forecast_kind: str) -> None:
    if forecast_kind == "dividends" and asset_class not in ("stock", "etf"):
        raise ValueError(
            f"--forecast-kind dividends is stock/etf only, got --asset-class {asset_class!r}."
        )
    if forecast_kind == "price-bands" and asset_class not in (
        "stock",
        "etf",
        "fx",
        "benchmark",
        "future",
    ):
        raise ValueError(
            "--forecast-kind price-bands is stock/etf/fx/benchmark/future only, got "
            f"--asset-class {asset_class!r}."
        )


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


def _load_benchmarks(config: Path | None, benchmarks_json: str | None) -> list[BenchmarkRef]:
    if benchmarks_json is not None:
        return parse_benchmarks_json(benchmarks_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_benchmarks(config)


def _load_futures(config: Path | None, futures_json: str | None) -> list[FutureRef]:
    if futures_json is not None:
        return parse_futures_json(futures_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_futures(config)


def _dividend_forecast_task(
    ticker: str, datafeed: DatafeedClient, output_dir: Path, asset_class: str, years: int
) -> Path | None:
    logger.info("Forecasting dividends for %s", ticker)
    dividends_client = DividendsClient(ticker, datafeed=datafeed)
    history = dividends_client.dividends(full_load=True)
    forecast = dividends(history, years=years)
    return write_dividend_forecast_parquet(forecast, output_dir, asset_class)


def _price_records(datafeed: DatafeedClient, symbol: str) -> list[dict[str, float | str]]:
    """The minimal `{date, close}` records `fx_price_bands()`/
    `stock_price_bands()` need, read straight off `DatafeedClient.
    get_history` — no `equicast-fx`/`equicast-stock` dependency (see this
    module's own docstring for why)."""
    history = datafeed.get_history(symbol, period=FULL_HISTORY_PERIOD)
    return [
        {"date": index.date().isoformat(), "close": float(row["Close"])}
        for index, row in history.iterrows()
    ]


def _fx_forecast_task(
    pair: FxPairRef, datafeed: DatafeedClient, output_dir: Path, years: int
) -> Path | None:
    logger.info("Forecasting FX price bands for %s%s", pair.from_currency, pair.to_currency)
    symbol = f"{pair.from_currency}{pair.to_currency}=X"
    prices = _price_records(datafeed, symbol)
    forecast = fx_price_bands(
        prices, pair.from_currency, pair.to_currency, datafeed=datafeed, years=years
    )
    return write_fx_price_bands_parquet(forecast, output_dir)


def _stock_forecast_task(
    ticker: str,
    datafeed: DatafeedClient,
    output_dir: Path,
    years: int,
    num_paths: int,
    routing_failures: list[tuple[str, Exception]],
) -> Path | None:
    logger.info("Forecasting stock price bands for %s", ticker)
    info = datafeed.get_info(ticker)
    prices = _price_records(datafeed, ticker)
    try:
        forecast = stock_price_bands(
            prices,
            ticker,
            info.get("sector"),
            info.get("industry"),
            datafeed=datafeed,
            years=years,
            num_paths=num_paths,
        )
    except UnroutableSectorError as error:
        logger.error("Skipping %s: %s", ticker, error)
        routing_failures.append((ticker, error))
        return None
    return write_stock_price_bands_parquet(forecast, output_dir)


def _etf_forecast_task(
    ticker: str,
    datafeed: DatafeedClient,
    output_dir: Path,
    years: int,
    num_paths: int,
    routing_failures: list[tuple[str, Exception]],
) -> Path | None:
    logger.info("Forecasting ETF price bands for %s", ticker)
    info = datafeed.get_info(ticker)
    prices = _price_records(datafeed, ticker)
    try:
        forecast = etf_price_bands(
            prices,
            ticker,
            info.get("category"),
            datafeed=datafeed,
            years=years,
            num_paths=num_paths,
        )
    except UnroutableEtfTypeError as error:
        logger.error("Skipping %s: %s", ticker, error)
        routing_failures.append((ticker, error))
        return None
    return write_etf_price_bands_parquet(forecast, output_dir)


def _benchmark_forecast_task(
    benchmark: BenchmarkRef,
    datafeed: DatafeedClient,
    output_dir: Path,
    years: int,
    num_paths: int,
    routing_failures: list[tuple[str, Exception]],
) -> Path | None:
    logger.info("Forecasting benchmark price bands for %s", benchmark.key)
    prices = _price_records(datafeed, benchmark.symbol)
    try:
        forecast = benchmark_price_bands(prices, benchmark.key, years=years, num_paths=num_paths)
    except UnroutableBenchmarkError as error:
        logger.error("Skipping %s: %s", benchmark.key, error)
        routing_failures.append((benchmark.key, error))
        return None
    return write_benchmark_price_bands_parquet(forecast, output_dir)


def _future_forecast_task(
    future_ref: FutureRef,
    datafeed: DatafeedClient,
    output_dir: Path,
    years: int,
    num_paths: int,
    routing_failures: list[tuple[str, Exception]],
) -> Path | None:
    logger.info("Forecasting future price bands for %s", future_ref.key)
    prices = _price_records(datafeed, future_ref.symbol)
    try:
        forecast = future_price_bands(prices, future_ref.key, years=years, num_paths=num_paths)
    except UnroutableCommodityError as error:
        logger.error("Skipping %s: %s", future_ref.key, error)
        routing_failures.append((future_ref.key, error))
        return None
    return write_future_price_bands_parquet(forecast, output_dir)


def run(
    asset_class: str,
    forecast_kind: str,
    config: Path | None,
    output_dir: Path,
    tickers_json: str | None = None,
    pairs_json: str | None = None,
    benchmarks_json: str | None = None,
    futures_json: str | None = None,
    years: int = 10,
    num_paths: int = DEFAULT_NUM_PATHS,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> list[Path]:
    _validate_forecast_kind(asset_class, forecast_kind)
    _validate_source_for_asset_class(
        asset_class, tickers_json, pairs_json, benchmarks_json, futures_json
    )

    # One DatafeedClient (and its rate limiter) shared across every worker, so
    # the configured request rate is a real ceiling regardless of concurrency.
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)

    routing_failures: list[tuple[str, Exception]] = []
    tasks: list[Callable[[], Path | None]]
    if forecast_kind == "price-bands" and asset_class == "fx":
        pairs = _load_fx_pairs(config, pairs_json)
        tasks = [partial(_fx_forecast_task, pair, datafeed, output_dir, years) for pair in pairs]
    elif forecast_kind == "price-bands" and asset_class == "future":
        future_refs = _load_futures(config, futures_json)
        tasks = [
            partial(
                _future_forecast_task,
                future_ref,
                datafeed,
                output_dir,
                years,
                num_paths,
                routing_failures,
            )
            for future_ref in future_refs
        ]
    elif forecast_kind == "price-bands" and asset_class == "benchmark":
        benchmarks = _load_benchmarks(config, benchmarks_json)
        tasks = [
            partial(
                _benchmark_forecast_task,
                benchmark,
                datafeed,
                output_dir,
                years,
                num_paths,
                routing_failures,
            )
            for benchmark in benchmarks
        ]
    elif forecast_kind == "price-bands" and asset_class == "etf":
        tickers = _load_tickers(config, tickers_json)
        tasks = [
            partial(
                _etf_forecast_task,
                ticker,
                datafeed,
                output_dir,
                years,
                num_paths,
                routing_failures,
            )
            for ticker in tickers
        ]
    elif forecast_kind == "price-bands":  # stock
        tickers = _load_tickers(config, tickers_json)
        tasks = [
            partial(
                _stock_forecast_task,
                ticker,
                datafeed,
                output_dir,
                years,
                num_paths,
                routing_failures,
            )
            for ticker in tickers
        ]
    else:  # dividends, stock/etf
        tickers = _load_tickers(config, tickers_json)
        tasks = [
            partial(_dividend_forecast_task, ticker, datafeed, output_dir, asset_class, years)
            for ticker in tickers
        ]

    written: list[Path] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task) for task in tasks]
        for future in as_completed(futures):
            path = future.result()
            if path is not None:
                written.append(path)

    if routing_failures:
        summary = "; ".join(f"{ticker} ({error})" for ticker, error in routing_failures)
        raise ForecastBatchError(
            f"{len(routing_failures)} ticker(s) failed to route to a forecasting schema: {summary}"
        )
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    written = run(
        args.asset_class,
        args.forecast_kind,
        args.config,
        args.out,
        tickers_json=args.tickers_json,
        pairs_json=args.pairs_json,
        benchmarks_json=args.benchmarks_json,
        futures_json=args.futures_json,
        years=args.years,
        num_paths=args.num_paths,
        max_workers=args.max_workers,
        max_calls=args.max_calls,
        period_seconds=args.period_seconds,
    )
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
