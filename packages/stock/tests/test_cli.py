from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from equicast_stock.cli import run


def _fake_stock_client_factory(created: list[MagicMock] | None = None):
    def fake_stock_client(ticker: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = ticker
        client.profile.return_value = {
            "ticker": ticker,
            "name": f"{ticker} Inc.",
            "quote_type": "EQUITY",
            "exchange": "NMS",
            "currency": "USD",
            "description": f"{ticker} description.",
            "sector": "Technology",
            "industry": "Software",
            "website": f"https://{ticker.lower()}.example.com",
            "beta": 1.0,
            "payout_ratio": None,
            "dividend_rate": None,
            "dividend_yield": None,
            "market_cap": 1000000000,
            "volume": 1000000,
            "day_open": 10.0,
            "day_high": 10.5,
            "day_low": 9.5,
            "day_close": 10.2,
            "year_open": 8.0,
            "year_high": 12.0,
            "year_low": 7.0,
            "year_close": 10.2,
            "address": "1 Some Street, Somewhere, CA 00000",
            "country": "United States",
            "region": "North America",
            "full_time_employees": 1000,
            "ceos": [{"name": "Someone", "role": "CEO"}],
            "ipo_date": "2000-01-01T00:00:00+00:00",
            "last_updated": "2026-08-28T21:29:05+00:00",
            "source": "yfinance",
        }
        client.prices.return_value = [
            {
                "ticker": ticker,
                "currency": "USD",
                "date": "2026-01-15",
                "open": 10.0,
                "high": 10.5,
                "low": 9.5,
                "close": 10.2,
                "average": 10.0,
                "last_updated": "2026-08-28T21:29:05+00:00",
                "source": "yfinance",
            }
        ]
        if created is not None:
            created.append(client)
        return client

    return fake_stock_client


def _fake_dividends_client_factory(
    created: list[MagicMock] | None = None,
    records: list[dict] | None = None,
    future_records: list[dict] | None = None,
):
    def fake_dividends_client(symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = symbol
        client.dividends.return_value = records or [
            {
                "ticker": symbol,
                "currency": "USD",
                "ex_dividend_date": "2026-02-10",
                "price": 0.26,
                "last_updated": "2026-08-30T09:00:02+00:00",
                "source": "yfinance",
            }
        ]
        # No future dividend by default - most tickers don't have one (see
        # DividendsClient.future_dividends' docstring), and write_future_
        # dividend_parquet omits the file entirely for an empty list, so
        # existing tests' written-file-count assertions stay unaffected.
        client.future_dividends.return_value = future_records or []
        if created is not None:
            created.append(client)
        return client

    return fake_dividends_client


def _fake_events_client_factory(created: list[MagicMock] | None = None):
    def fake_events_client(symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = symbol
        client.events.return_value = [
            {
                "ticker": symbol,
                "event_type": "earnings",
                "date": "2026-01-30",
                "eps_estimate": None,
                "reported_eps": 2.18,
                "surprise_pct": -3.5,
                "firm": None,
                "from_grade": None,
                "to_grade": None,
                "action": None,
                "price_target_action": None,
                "current_price_target": None,
                "prior_price_target": None,
                "ratio": None,
                "last_updated": "2026-08-30T09:00:03+00:00",
                "source": "yfinance",
            }
        ]
        if created is not None:
            created.append(client)
        return client

    return fake_events_client


def _fake_metrics_client_factory(created: list[MagicMock] | None = None):
    def fake_metrics_client(symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = symbol
        client.metrics.return_value = {
            "volatility": 0.24,
            "sharpe_ratio": 0.81,
            "max_drawdown": -0.18,
            "cagr_1y": 0.21,
            "cagr_2y": 0.15,
            "cagr_3y": 0.12,
            "cagr_5y": 0.19,
            "cagr_10y": 0.22,
            "last_updated": "2026-08-30T09:00:00+00:00",
            "source": "equicast",
        }
        client.fundamentals.return_value = {
            "trailing_pe": 30.1,
            "forward_pe": 27.4,
            "trailing_eps": 6.13,
            "forward_eps": 6.75,
            "peg": 2.05,
            "price_to_book": 45.2,
            "price_to_sales": 8.1,
            "ev_ebitda": 21.3,
            "gross_margin": 0.462,
            "operating_margin": 0.312,
            "profit_margin": 0.24,
            "return_on_equity": 1.52,
            "return_on_assets": 0.29,
            "debt_to_equity": 148.6,
            "free_cash_flow_per_share": 6.42,
            "last_updated": "2026-08-30T09:00:01+00:00",
            "source": "yfinance",
        }
        client.buy_sell_pressure.return_value = {
            "buyers_pct": 0.62,
            "sellers_pct": 0.38,
        }
        if created is not None:
            created.append(client)
        return client

    return fake_metrics_client


def _fake_news_client_factory(
    created: list[MagicMock] | None = None, records: list[dict] | None = None
):
    def fake_news_client(symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = symbol
        client.news.return_value = (
            records
            if records is not None
            else [
                {
                    "ticker": symbol,
                    "id": "abc123",
                    "title": "Some headline",
                    "summary": "Some summary",
                    "publisher": "Reuters",
                    "url": "https://example.com/click",
                    "thumbnail_url": "https://example.com/thumb.jpg",
                    "published_at": "2026-08-30T09:00:00+00:00",
                    "last_updated": "2026-08-30T09:00:04+00:00",
                    "source": "yfinance",
                }
            ]
        )
        if created is not None:
            created.append(client)
        return client

    return fake_news_client


def _patch_clients(
    stock_created: list[MagicMock] | None = None,
    dividends_created: list[MagicMock] | None = None,
    events_created: list[MagicMock] | None = None,
    metrics_created: list[MagicMock] | None = None,
    news_created: list[MagicMock] | None = None,
    dividend_records: list[dict] | None = None,
    future_dividend_records: list[dict] | None = None,
    news_records: list[dict] | None = None,
):
    return (
        patch("equicast_stock.cli.DatafeedClient"),
        patch(
            "equicast_stock.cli.StockClient", side_effect=_fake_stock_client_factory(stock_created)
        ),
        patch(
            "equicast_stock.cli.DividendsClient",
            side_effect=_fake_dividends_client_factory(
                dividends_created, records=dividend_records, future_records=future_dividend_records
            ),
        ),
        patch(
            "equicast_stock.cli.EventsClient",
            side_effect=_fake_events_client_factory(events_created),
        ),
        patch(
            "equicast_stock.cli.MetricsClient",
            side_effect=_fake_metrics_client_factory(metrics_created),
        ),
        patch(
            "equicast_stock.cli.NewsClient",
            side_effect=_fake_news_client_factory(news_created, records=news_records),
        ),
    )


def test_run_writes_profile_price_dividend_events_metrics_and_news_parquet_per_configured_ticker(
    tmp_path: Path,
) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text("tickers:\n  - AAPL\n  - MSFT\n")
    out_dir = tmp_path / "output"

    patches = _patch_clients()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        written = run(config, out_dir)

    assert len(written) == 12  # profile + price + dividend + events + metrics + news per ticker
    for ticker in ("AAPL", "MSFT"):
        assert (out_dir / f"stock={ticker}" / "profile.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "price" / "current.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "dividend" / "current.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "events" / "current.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "metrics.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "news.parquet").exists()


def test_run_derives_dividend_frequency_into_profile_parquet(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    quarterly_records = [
        {
            "ticker": "AAPL",
            "currency": "USD",
            "ex_dividend_date": date,
            "price": 0.26,
            "last_updated": "2026-08-30T09:00:02+00:00",
            "source": "yfinance",
        }
        for date in ("2025-02-10", "2025-05-10", "2025-08-10", "2025-11-10", "2026-02-10")
    ]

    patches = _patch_clients(dividend_records=quarterly_records)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        run(None, out_dir, tickers_json='["AAPL"]')

    profile = pd.read_parquet(out_dir / "stock=AAPL" / "profile.parquet")
    assert profile["dividend_frequency"].iloc[0] == "quarterly"


def test_run_dividend_frequency_is_not_applicable_with_too_little_history(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "output"

    # Default fixture dividends_client returns exactly one record.
    patches = _patch_clients()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        run(None, out_dir, tickers_json='["AAPL"]')

    profile = pd.read_parquet(out_dir / "stock=AAPL" / "profile.parquet")
    assert profile["dividend_frequency"].iloc[0] == "not_applicable"


def test_run_writes_future_dividend_parquet_when_a_future_dividend_exists(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "output"
    future_records = [
        {
            "ticker": "MNG.L",
            "currency": "GBp",
            "ex_dividend_date": "2026-09-10",
            "payment_date": "2026-10-15",
            "price": 0.068,
            "last_updated": "2026-08-30T09:00:02+00:00",
            "source": "yfinance",
        }
    ]

    patches = _patch_clients(future_dividend_records=future_records)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        written = run(None, out_dir, tickers_json='["MNG.L"]')

    path = out_dir / "stock=MNG.L" / "dividend" / "future.parquet"
    assert path in written
    assert pd.read_parquet(path).to_dict(orient="records") == future_records


def test_run_omits_future_dividend_parquet_when_none_exists(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    # Default fixture dividends_client returns no future dividend.
    patches = _patch_clients()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        run(None, out_dir, tickers_json='["AAPL"]')

    assert not (out_dir / "stock=AAPL" / "dividend" / "future.parquet").exists()


def test_run_omits_news_parquet_when_no_news_published(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    patches = _patch_clients(news_records=[])
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        run(None, out_dir, tickers_json='["AAPL"]')

    assert not (out_dir / "stock=AAPL" / "news.parquet").exists()


def test_run_accepts_tickers_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["AAPL"]'

    patches = _patch_clients()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        written = run(None, out_dir, tickers_json=tickers_json)

    assert set(written) == {
        out_dir / "stock=AAPL" / "profile.parquet",
        out_dir / "stock=AAPL" / "price" / "current.parquet",
        out_dir / "stock=AAPL" / "dividend" / "current.parquet",
        out_dir / "stock=AAPL" / "events" / "current.parquet",
        out_dir / "stock=AAPL" / "metrics.parquet",
        out_dir / "stock=AAPL" / "news.parquet",
    }


def test_run_passes_full_load_through_to_prices_and_events(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["AAPL"]'
    stock_created: list[MagicMock] = []
    dividends_created: list[MagicMock] = []
    events_created: list[MagicMock] = []
    metrics_created: list[MagicMock] = []
    news_created: list[MagicMock] = []

    with (
        patch("equicast_stock.cli.DatafeedClient"),
        patch(
            "equicast_stock.cli.StockClient",
            side_effect=_fake_stock_client_factory(stock_created),
        ),
        patch(
            "equicast_stock.cli.DividendsClient",
            side_effect=_fake_dividends_client_factory(dividends_created),
        ),
        patch(
            "equicast_stock.cli.EventsClient",
            side_effect=_fake_events_client_factory(events_created),
        ),
        patch(
            "equicast_stock.cli.MetricsClient",
            side_effect=_fake_metrics_client_factory(metrics_created),
        ),
        patch(
            "equicast_stock.cli.NewsClient",
            side_effect=_fake_news_client_factory(news_created),
        ),
    ):
        run(None, out_dir, tickers_json=tickers_json, full_load=True)

    assert len(stock_created) == 1  # one StockClient per ticker, shared by profile + prices tasks
    stock_created[0].prices.assert_called_once_with(full_load=True)
    assert len(events_created) == 1
    events_created[0].events.assert_called_once_with(full_load=True)
    assert len(metrics_created) == 1
    metrics_created[0].metrics.assert_called_once_with()  # full_load doesn't affect metrics
    metrics_created[0].fundamentals.assert_called_once_with()
    metrics_created[0].buy_sell_pressure.assert_called_once_with()
    assert len(news_created) == 1
    news_created[0].news.assert_called_once_with()  # full_load doesn't affect news either

    # dividends() is always called with full_load=True regardless of run()'s own
    # full_load flag - see _profile_and_dividends_task's docstring for why (it
    # fetches this ticker's entire dividend series either way, so calling it once
    # with full_load=True and filtering client-side for what to write costs no
    # more yfinance calls than passing full_load through unconditionally would).
    assert len(dividends_created) == 1
    dividends_created[0].dividends.assert_called_once_with(full_load=True)


def test_run_still_fetches_full_dividend_history_when_full_load_is_false(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "output"
    dividends_created: list[MagicMock] = []

    patches = _patch_clients(dividends_created=dividends_created)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        run(None, out_dir, tickers_json='["AAPL"]', full_load=False)

    assert len(dividends_created) == 1
    dividends_created[0].dividends.assert_called_once_with(full_load=True)


def test_run_combines_risk_metrics_and_fundamentals_into_one_metrics_parquet(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["AAPL"]'

    patches = _patch_clients()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        run(None, out_dir, tickers_json=tickers_json)

    metrics = pd.read_parquet(out_dir / "stock=AAPL" / "metrics.parquet").to_dict(orient="records")[
        0
    ]
    assert metrics["ticker"] == "AAPL"
    assert metrics["volatility"] == 0.24  # from metrics()
    assert metrics["trailing_pe"] == 30.1  # from fundamentals()
    assert metrics["buyers_pct"] == 0.62  # from buy_sell_pressure()
    assert metrics["sellers_pct"] == 0.38
    # fundamentals() was fetched a moment after metrics(), so its
    # last_updated wins the merge; source stays "equicast" since metrics()
    # always reports that (see MetricsClient.metrics()'s docstring).
    assert metrics["last_updated"] == "2026-08-30T09:00:01+00:00"
    assert metrics["source"] == "equicast"


def test_run_shares_one_datafeed_client_across_workers(tmp_path: Path) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text("tickers:\n  - AAPL\n  - MSFT\n")
    out_dir = tmp_path / "output"

    with (
        patch("equicast_stock.cli.DatafeedClient") as mock_datafeed_cls,
        patch(
            "equicast_stock.cli.StockClient", side_effect=_fake_stock_client_factory()
        ) as mock_client,
        patch(
            "equicast_stock.cli.DividendsClient", side_effect=_fake_dividends_client_factory()
        ) as mock_dividends_client,
        patch(
            "equicast_stock.cli.EventsClient", side_effect=_fake_events_client_factory()
        ) as mock_events_client,
        patch(
            "equicast_stock.cli.MetricsClient", side_effect=_fake_metrics_client_factory()
        ) as mock_metrics_client,
        patch(
            "equicast_stock.cli.NewsClient", side_effect=_fake_news_client_factory()
        ) as mock_news_client,
    ):
        run(config, out_dir, max_workers=2, max_calls=5, period_seconds=2.0)

    mock_datafeed_cls.assert_called_once_with(max_calls=5, period_seconds=2.0)
    shared_datafeed = mock_datafeed_cls.return_value
    for call in mock_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
    for call in mock_dividends_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
    for call in mock_events_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
    for call in mock_metrics_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
    for call in mock_news_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
