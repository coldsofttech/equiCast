"""CLI: extract a profile, daily prices, dividends, events, and risk
metrics for every configured ETF ticker.

For each ticker, writes one profile.parquet snapshot (including a
`dividend_frequency` field derived from dividend history - see
`equicast_dividends.dividend_frequency`), a price/current.parquet and
dividend/current.parquet (plus price/history.parquet and
dividend/history.parquet too, but only on a --full-load run), a
dividend/future.parquet when yfinance reports a still-upcoming dividend for
this ticker (see `equicast_dividends.DividendsClient.future_dividends` -
omitted entirely otherwise, not written empty), an events/current.parquet
(and events/history.parquet on --full-load), one metrics.parquet
snapshot (volatility, Sharpe ratio, max drawdown, CAGR, and a
buyers_pct/sellers_pct buy/sell volume-pressure gauge), and a
news.parquet of the ticker's news articles from the trailing month
(omitted entirely when there's none - see equicast-news).
metrics.parquet carries MetricsClient.metrics() and .buy_sell_pressure() -
not .fundamentals(), which is stock-only and mostly None/unreliable for ETFs.
events.parquet in practice only ever has "split" rows for an ETF ticker -
earnings/analyst-rating events are always empty, since yfinance has no
earnings or analyst coverage for a fund - but splits are real (e.g. QQQ's
2000 2-for-1, VTI's 2008 2-for-1). Profile and dividends are fetched
together as one task (both need the same dividend history - see
`_profile_and_dividends_task`); prices, events, metrics, and news are four
further independent tasks - all five for a given ticker submitted to the
same worker pool, so they run concurrently rather than one after the other.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from equicast_datafeed import DatafeedClient
from equicast_dividends import DividendsClient, dividend_frequency
from equicast_events import EventsClient
from equicast_metrics import MetricsClient
from equicast_news import NewsClient

from equicast_etf.client import ETFClient
from equicast_etf.config import ETFTicker, load_etf_tickers, parse_etf_tickers_json
from equicast_etf.writer import (
    write_dividend_parquet,
    write_events_parquet,
    write_failures_manifest,
    write_future_dividend_parquet,
    write_metrics_parquet,
    write_news_parquet,
    write_price_parquet,
    write_profile_parquet,
)

logger = logging.getLogger(__name__)

#: v1 tax logic only models these two domiciles (GitHub issue #94) — an
#: ISIN prefix outside this map (or a missing ISIN) leaves `tax_domicile`
#: unset, same as an unmodeled asset class leaving other profile fields
#: `None` elsewhere in this pipeline.
_ISIN_COUNTRY_TAX_DOMICILE = {"GB": "UK", "US": "US"}


def _derive_tax_domicile(isin: str | None) -> str | None:
    """Best-effort `tax_domicile` from an ISIN's leading 2-letter country
    code (ISO 6166) — `None` for an unset ISIN or a country this v1 model
    doesn't cover. Only a default: a config entry's own `tax_domicile`
    (see `ETFTicker`) always wins over this, the same way `isin_override`
    wins over yfinance's own lookup."""
    if not isin:
        return None
    return _ISIN_COUNTRY_TAX_DOMICILE.get(isin[:2].upper())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract ETF ticker profiles, daily prices, dividends, events, and risk "
        "metrics, writing all five as Parquet."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path, help="Path to an ETF tickers YAML config.")
    source.add_argument(
        "--tickers-json",
        help="JSON array of ticker strings, or {ticker, isin, tax_domicile} objects for an "
        "ISIN/tax_domicile override (e.g. one matrix chunk).",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Output directory for Parquet files."
    )
    parser.add_argument(
        "--full-load",
        action="store_true",
        help="Fetch each ticker's entire yfinance history (prices, dividends, and events) "
        "instead of just the current year.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Profile/price/dividend/events/metrics fetches run concurrently, up to this "
        "many at once (default: 1).",
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


def _load_tickers(config: Path | None, tickers_json: str | None) -> list[ETFTicker]:
    if tickers_json is not None:
        return parse_etf_tickers_json(tickers_json)
    assert config is not None  # enforced by the mutually-exclusive required group
    return load_etf_tickers(config)


def _profile_and_dividends_task(
    client: ETFClient,
    dividends_client: DividendsClient,
    output_dir: Path,
    key: str,
    full_load: bool,
    isin_override: str | None = None,
    tax_domicile_override: str | None = None,
) -> list[Path]:
    """Write profile.parquet (with a `dividend_frequency` field derived from
    dividend history), dividend/current.parquet (plus
    dividend/history.parquet on a --full-load run), and dividend/future.parquet
    when yfinance reports a still-upcoming dividend (see
    `DividendsClient.future_dividends` - omitted entirely when there isn't
    one, regardless of `full_load`).

    Combined into one task, rather than two independent ones like
    prices/events, because both need the same dividend history:
    `DividendsClient.dividends()` fetches this ticker's *entire* yfinance
    dividend series regardless of its own `full_load` argument — that flag
    only controls a post-fetch filter (see its docstring) — so calling it
    once with `full_load=True` here and filtering client-side for what to
    write costs no more yfinance calls than the old separate profile/
    dividends tasks did, while a naive merge that just called `dividends()`
    a second time from `_profile_task` would have doubled them.

    `profile["tax_domicile"]` (GitHub issue #94) is `tax_domicile_override`
    when the config gave one, else derived from the (possibly just-
    overridden) `isin` via `_derive_tax_domicile` — same override-wins-over-
    derived precedence `isin_override` itself has over yfinance's lookup.
    """
    logger.info("Fetching profile and dividends for %s (full_load=%s)", key, full_load)
    dividends = dividends_client.dividends(full_load=True)
    profile = {**client.profile(), "dividend_frequency": dividend_frequency(dividends)}
    if isin_override is not None:
        profile["isin"] = isin_override
    profile["tax_domicile"] = tax_domicile_override or _derive_tax_domicile(profile.get("isin"))
    paths = [write_profile_parquet(profile, output_dir)]

    if full_load:
        to_write = dividends
    else:
        current_year = str(datetime.now(UTC).year)
        to_write = [d for d in dividends if d["ex_dividend_date"][:4] == current_year]
    paths.extend(write_dividend_parquet(to_write, output_dir))
    paths.extend(write_future_dividend_parquet(dividends_client.future_dividends(), output_dir))
    return paths


def _prices_task(client: ETFClient, output_dir: Path, key: str, full_load: bool) -> list[Path]:
    logger.info("Fetching prices for %s (full_load=%s)", key, full_load)
    return write_price_parquet(client.prices(full_load=full_load), output_dir)


def _events_task(
    events_client: EventsClient, output_dir: Path, key: str, full_load: bool
) -> list[Path]:
    logger.info("Fetching events for %s (full_load=%s)", key, full_load)
    return write_events_parquet(events_client.events(full_load=full_load), output_dir)


def _metrics_task(metrics_client: MetricsClient, output_dir: Path, key: str) -> list[Path]:
    logger.info("Computing metrics for %s", key)
    # buy_sell_pressure() has no last_updated/source of its own to
    # reconcile (see its docstring) - just adds buyers_pct/sellers_pct
    # alongside whatever metrics() already returned.
    combined = {**metrics_client.metrics(), **metrics_client.buy_sell_pressure()}
    return [write_metrics_parquet(combined, metrics_client.symbol, output_dir)]


def _news_task(news_client: NewsClient, output_dir: Path, key: str) -> list[Path]:
    logger.info("Fetching news for %s", key)
    return write_news_parquet(news_client.news(), output_dir)


def run(
    config: Path | None,
    output_dir: Path,
    tickers_json: str | None = None,
    full_load: bool = False,
    max_workers: int = 1,
    max_calls: int = 1,
    period_seconds: float = 1.0,
) -> list[Path]:
    tickers = _load_tickers(config, tickers_json)

    # One DatafeedClient (and its rate limiter) shared across every worker, so
    # the configured request rate is a real ceiling regardless of concurrency.
    datafeed = DatafeedClient(max_calls=max_calls, period_seconds=period_seconds)

    # One ETFClient/DividendsClient/EventsClient/MetricsClient/NewsClient
    # per ticker, shared by that ticker's profile+dividends, prices, events,
    # metrics, and news tasks — all five only read immutable state and
    # delegate to the (thread-safe) shared datafeed, so calling them
    # concurrently on one instance is safe.
    #
    # Each task is tagged with its ticker key and a short task label (rather
    # than a bare callable) so a failure below can be attributed back to
    # "which ticker, which piece" for failures.json - see equicast-support#145.
    tasks: list[tuple[str, str, Callable[[], list[Path]]]] = []
    for ticker in tickers:
        client = ETFClient(ticker.ticker, datafeed=datafeed)
        dividends_client = DividendsClient(client.symbol, datafeed=datafeed)
        events_client = EventsClient(client.symbol, datafeed=datafeed)
        metrics_client = MetricsClient(client.symbol, datafeed=datafeed)
        news_client = NewsClient(client.symbol, datafeed=datafeed)
        tasks.append(
            (
                ticker.key,
                "profile/dividends",
                partial(
                    _profile_and_dividends_task,
                    client,
                    dividends_client,
                    output_dir,
                    ticker.key,
                    full_load,
                    ticker.isin,
                    ticker.tax_domicile,
                ),
            )
        )
        tasks.append(
            (ticker.key, "prices", partial(_prices_task, client, output_dir, ticker.key, full_load))
        )
        tasks.append(
            (
                ticker.key,
                "events",
                partial(_events_task, events_client, output_dir, ticker.key, full_load),
            )
        )
        tasks.append(
            (ticker.key, "metrics", partial(_metrics_task, metrics_client, output_dir, ticker.key))
        )
        tasks.append((ticker.key, "news", partial(_news_task, news_client, output_dir, ticker.key)))

    # A failed task no longer aborts the whole run (previously, the first
    # future.result() to raise propagated straight out of this loop, losing
    # every other ticker's already-fetched data too) - every other ticker's
    # tasks still complete and get written/returned. Each failure is instead
    # collected into failures.json (equicast-support#145) so the workflow can
    # report exactly which ticker/piece failed, rather than the whole chunk.
    written: list[Path] = []
    failures: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(task): (ticker_key, task_label)
            for ticker_key, task_label, task in tasks
        }
        for future in as_completed(future_to_task):
            ticker_key, task_label = future_to_task[future]
            try:
                written.extend(future.result())
            except Exception as exc:
                logger.exception("Failed to fetch %s for %s", task_label, ticker_key)
                failures.append({"ticker": ticker_key, "task": task_label, "error": str(exc)})

    write_failures_manifest(failures, output_dir)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_arg_parser().parse_args()
    for path in run(
        args.config,
        args.out,
        tickers_json=args.tickers_json,
        full_load=args.full_load,
        max_workers=args.max_workers,
        max_calls=args.max_calls,
        period_seconds=args.period_seconds,
    ):
        print(path)


if __name__ == "__main__":
    main()
