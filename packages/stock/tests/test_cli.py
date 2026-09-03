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
            "day_average": 10.0,
            "year_open": 8.0,
            "year_high": 12.0,
            "year_low": 7.0,
            "year_close": 10.2,
            "year_average": 9.5,
            "moving_average_50_days": 9.8,
            "moving_average_200_days": 9.0,
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


def _fake_dividends_client_factory(created: list[MagicMock] | None = None):
    def fake_dividends_client(symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = symbol
        client.dividends.return_value = [
            {
                "ticker": symbol,
                "currency": "USD",
                "ex_dividend_date": "2026-02-10",
                "price": 0.26,
                "last_updated": "2026-08-30T09:00:02+00:00",
                "source": "yfinance",
            }
        ]
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
        if created is not None:
            created.append(client)
        return client

    return fake_metrics_client


def _patch_clients(
    stock_created: list[MagicMock] | None = None,
    dividends_created: list[MagicMock] | None = None,
    events_created: list[MagicMock] | None = None,
    metrics_created: list[MagicMock] | None = None,
):
    return (
        patch("equicast_stock.cli.DatafeedClient"),
        patch(
            "equicast_stock.cli.StockClient", side_effect=_fake_stock_client_factory(stock_created)
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
    )


def test_run_writes_profile_price_dividend_events_and_metrics_parquet_per_configured_ticker(
    tmp_path: Path,
) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text("tickers:\n  - AAPL\n  - MSFT\n")
    out_dir = tmp_path / "output"

    datafeed_patch, stock_patch, dividends_patch, events_patch, metrics_patch = _patch_clients()
    with datafeed_patch, stock_patch, dividends_patch, events_patch, metrics_patch:
        written = run(config, out_dir)

    assert len(written) == 10  # profile + price + dividend + events + metrics per ticker
    for ticker in ("AAPL", "MSFT"):
        assert (out_dir / f"stock={ticker}" / "profile.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "price" / "current.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "year=2026" / "dividend.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "year=2026" / "events.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "metrics.parquet").exists()


def test_run_accepts_tickers_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["AAPL"]'

    datafeed_patch, stock_patch, dividends_patch, events_patch, metrics_patch = _patch_clients()
    with datafeed_patch, stock_patch, dividends_patch, events_patch, metrics_patch:
        written = run(None, out_dir, tickers_json=tickers_json)

    assert set(written) == {
        out_dir / "stock=AAPL" / "profile.parquet",
        out_dir / "stock=AAPL" / "price" / "current.parquet",
        out_dir / "stock=AAPL" / "year=2026" / "dividend.parquet",
        out_dir / "stock=AAPL" / "year=2026" / "events.parquet",
        out_dir / "stock=AAPL" / "metrics.parquet",
    }


def test_run_passes_full_load_through_to_prices_dividends_and_events(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["AAPL"]'
    stock_created: list[MagicMock] = []
    dividends_created: list[MagicMock] = []
    events_created: list[MagicMock] = []
    metrics_created: list[MagicMock] = []

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
    ):
        run(None, out_dir, tickers_json=tickers_json, full_load=True)

    assert len(stock_created) == 1  # one StockClient per ticker, shared by profile + prices tasks
    stock_created[0].prices.assert_called_once_with(full_load=True)
    assert len(dividends_created) == 1
    dividends_created[0].dividends.assert_called_once_with(full_load=True)
    assert len(events_created) == 1
    events_created[0].events.assert_called_once_with(full_load=True)
    assert len(metrics_created) == 1
    metrics_created[0].metrics.assert_called_once_with()  # full_load doesn't affect metrics
    metrics_created[0].fundamentals.assert_called_once_with()


def test_run_combines_risk_metrics_and_fundamentals_into_one_metrics_parquet(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["AAPL"]'

    datafeed_patch, stock_patch, dividends_patch, events_patch, metrics_patch = _patch_clients()
    with datafeed_patch, stock_patch, dividends_patch, events_patch, metrics_patch:
        run(None, out_dir, tickers_json=tickers_json)

    metrics = pd.read_parquet(out_dir / "stock=AAPL" / "metrics.parquet").to_dict(orient="records")[
        0
    ]
    assert metrics["ticker"] == "AAPL"
    assert metrics["volatility"] == 0.24  # from metrics()
    assert metrics["trailing_pe"] == 30.1  # from fundamentals()
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
