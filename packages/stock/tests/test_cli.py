from pathlib import Path
from unittest.mock import MagicMock, patch

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


def _patch_clients(created: list[MagicMock] | None = None):
    return (
        patch("equicast_stock.cli.DatafeedClient"),
        patch("equicast_stock.cli.StockClient", side_effect=_fake_stock_client_factory(created)),
    )


def test_run_writes_profile_and_price_parquet_per_configured_ticker(tmp_path: Path) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text("tickers:\n  - AAPL\n  - MSFT\n")
    out_dir = tmp_path / "output"

    datafeed_patch, stock_patch = _patch_clients()
    with datafeed_patch, stock_patch:
        written = run(config, out_dir)

    assert len(written) == 4  # profile + price per ticker
    for ticker in ("AAPL", "MSFT"):
        assert (out_dir / f"stock={ticker}" / "profile.parquet").exists()
        assert (out_dir / f"stock={ticker}" / "year=2026" / "price.parquet").exists()


def test_run_accepts_tickers_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["AAPL"]'

    datafeed_patch, stock_patch = _patch_clients()
    with datafeed_patch, stock_patch:
        written = run(None, out_dir, tickers_json=tickers_json)

    assert set(written) == {
        out_dir / "stock=AAPL" / "profile.parquet",
        out_dir / "stock=AAPL" / "year=2026" / "price.parquet",
    }


def test_run_passes_full_load_through_to_prices_only(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    tickers_json = '["AAPL"]'
    created: list[MagicMock] = []

    with (
        patch("equicast_stock.cli.DatafeedClient"),
        patch("equicast_stock.cli.StockClient", side_effect=_fake_stock_client_factory(created)),
    ):
        run(None, out_dir, tickers_json=tickers_json, full_load=True)

    assert len(created) == 1  # one StockClient per ticker, shared by profile + prices tasks
    created[0].prices.assert_called_once_with(full_load=True)


def test_run_shares_one_datafeed_client_across_workers(tmp_path: Path) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text("tickers:\n  - AAPL\n  - MSFT\n")
    out_dir = tmp_path / "output"

    with (
        patch("equicast_stock.cli.DatafeedClient") as mock_datafeed_cls,
        patch(
            "equicast_stock.cli.StockClient", side_effect=_fake_stock_client_factory()
        ) as mock_client,
    ):
        run(config, out_dir, max_workers=2, max_calls=5, period_seconds=2.0)

    mock_datafeed_cls.assert_called_once_with(max_calls=5, period_seconds=2.0)
    shared_datafeed = mock_datafeed_cls.return_value
    for call in mock_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
