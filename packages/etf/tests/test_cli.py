from pathlib import Path
from unittest.mock import MagicMock, patch

from equicast_etf.cli import run


def _fake_etf_client_factory(created: list[MagicMock] | None = None):
    def fake_etf_client(ticker: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = ticker
        client.profile.return_value = {
            "ticker": ticker,
            "name": f"{ticker} Trust",
            "quote_type": "ETF",
            "exchange": "PCX",
            "currency": "USD",
            "description": f"{ticker} description.",
            "category": "Large Blend",
            "fund_family": "Example Family",
            "website": "https://example.com",
            "beta": 1.0,
            "expense_ratio": 0.03,
            "dividend_rate": None,
            "dividend_yield": 0.01,
            "total_assets": 1000000000,
            "nav_price": 100.0,
            "volume": 1000000,
            "day_open": 100.0,
            "day_high": 101.0,
            "day_low": 99.0,
            "day_close": 100.5,
            "day_average": 100.0,
            "year_open": 90.0,
            "year_high": 110.0,
            "year_low": 85.0,
            "year_close": 100.5,
            "year_average": 97.5,
            "moving_average_50_days": 99.0,
            "moving_average_200_days": 95.0,
            "ytd_return": 5.0,
            "three_year_average_return": 0.2,
            "five_year_average_return": 0.15,
            "inception_date": "2000-01-01T00:00:00+00:00",
            "last_updated": "2026-08-28T21:29:05+00:00",
            "source": "yfinance",
        }
        client.prices.return_value = [
            {
                "ticker": ticker,
                "currency": "USD",
                "date": "2026-01-15",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "average": 100.0,
                "last_updated": "2026-08-28T21:29:05+00:00",
                "source": "yfinance",
            }
        ]
        if created is not None:
            created.append(client)
        return client

    return fake_etf_client


def _fake_dividends_client_factory(created: list[MagicMock] | None = None):
    def fake_dividends_client(symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = symbol
        client.dividends.return_value = [
            {
                "ticker": symbol,
                "currency": "USD",
                "ex_dividend_date": "2026-02-10",
                "price": 1.85,
                "last_updated": "2026-08-30T09:00:02+00:00",
                "source": "yfinance",
            }
        ]
        if created is not None:
            created.append(client)
        return client

    return fake_dividends_client


def _fake_metrics_client_factory(created: list[MagicMock] | None = None):
    def fake_metrics_client(symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = symbol
        client.metrics.return_value = {
            "volatility": 0.13,
            "sharpe_ratio": 1.55,
            "max_drawdown": -0.09,
            "cagr_1y": 0.2,
            "cagr_2y": 0.19,
            "cagr_3y": 0.22,
            "cagr_5y": 0.13,
            "cagr_10y": 0.15,
            "last_updated": "2026-08-30T09:00:03+00:00",
            "source": "equicast",
        }
        if created is not None:
            created.append(client)
        return client

    return fake_metrics_client


def _patch_clients(
    etf_created: list[MagicMock] | None = None,
    dividends_created: list[MagicMock] | None = None,
    metrics_created: list[MagicMock] | None = None,
):
    return (
        patch("equicast_etf.cli.DatafeedClient"),
        patch("equicast_etf.cli.ETFClient", side_effect=_fake_etf_client_factory(etf_created)),
        patch(
            "equicast_etf.cli.DividendsClient",
            side_effect=_fake_dividends_client_factory(dividends_created),
        ),
        patch(
            "equicast_etf.cli.MetricsClient",
            side_effect=_fake_metrics_client_factory(metrics_created),
        ),
    )


def test_run_writes_profile_price_dividend_and_metrics_parquet_per_configured_ticker(
    tmp_path: Path,
) -> None:
    config = tmp_path / "etfs.yaml"
    config.write_text("tickers:\n  - VOO\n  - QQQ\n")
    out_dir = tmp_path / "output"

    datafeed_patch, etf_patch, dividends_patch, metrics_patch = _patch_clients()
    with datafeed_patch, etf_patch, dividends_patch, metrics_patch:
        written = run(config, out_dir)

    assert len(written) == 8  # profile + price + dividend + metrics per ticker
    for ticker in ("VOO", "QQQ"):
        assert (out_dir / f"etf={ticker}" / "profile.parquet").exists()
        assert (out_dir / f"etf={ticker}" / "year=2026" / "price.parquet").exists()
        assert (out_dir / f"etf={ticker}" / "year=2026" / "dividend.parquet").exists()
        assert (out_dir / f"etf={ticker}" / "metrics.parquet").exists()


def test_run_accepts_tickers_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["VOO"]'

    datafeed_patch, etf_patch, dividends_patch, metrics_patch = _patch_clients()
    with datafeed_patch, etf_patch, dividends_patch, metrics_patch:
        written = run(None, out_dir, tickers_json=tickers_json)

    assert set(written) == {
        out_dir / "etf=VOO" / "profile.parquet",
        out_dir / "etf=VOO" / "year=2026" / "price.parquet",
        out_dir / "etf=VOO" / "year=2026" / "dividend.parquet",
        out_dir / "etf=VOO" / "metrics.parquet",
    }


def test_run_passes_full_load_through_to_prices_and_dividends_only(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["VOO"]'
    etf_created: list[MagicMock] = []
    dividends_created: list[MagicMock] = []
    metrics_created: list[MagicMock] = []

    with (
        patch("equicast_etf.cli.DatafeedClient"),
        patch("equicast_etf.cli.ETFClient", side_effect=_fake_etf_client_factory(etf_created)),
        patch(
            "equicast_etf.cli.DividendsClient",
            side_effect=_fake_dividends_client_factory(dividends_created),
        ),
        patch(
            "equicast_etf.cli.MetricsClient",
            side_effect=_fake_metrics_client_factory(metrics_created),
        ),
    ):
        run(None, out_dir, tickers_json=tickers_json, full_load=True)

    assert len(etf_created) == 1  # one ETFClient per ticker, shared by profile + prices tasks
    etf_created[0].prices.assert_called_once_with(full_load=True)
    assert len(dividends_created) == 1
    dividends_created[0].dividends.assert_called_once_with(full_load=True)
    assert len(metrics_created) == 1
    metrics_created[0].metrics.assert_called_once_with()  # full_load doesn't affect metrics


def test_run_shares_one_datafeed_client_across_workers(tmp_path: Path) -> None:
    config = tmp_path / "etfs.yaml"
    config.write_text("tickers:\n  - VOO\n  - QQQ\n")
    out_dir = tmp_path / "output"

    with (
        patch("equicast_etf.cli.DatafeedClient") as mock_datafeed_cls,
        patch("equicast_etf.cli.ETFClient", side_effect=_fake_etf_client_factory()) as mock_client,
        patch(
            "equicast_etf.cli.DividendsClient", side_effect=_fake_dividends_client_factory()
        ) as mock_dividends_client,
        patch(
            "equicast_etf.cli.MetricsClient", side_effect=_fake_metrics_client_factory()
        ) as mock_metrics_client,
    ):
        run(config, out_dir, max_workers=2, max_calls=5, period_seconds=2.0)

    mock_datafeed_cls.assert_called_once_with(max_calls=5, period_seconds=2.0)
    shared_datafeed = mock_datafeed_cls.return_value
    for call in mock_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
    for call in mock_dividends_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
    for call in mock_metrics_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
