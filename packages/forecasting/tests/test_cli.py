from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from equicast_forecasting.cli import run


def _quarterly_records(ticker: str) -> list[dict]:
    end_year = date.today().year - 1
    records = []
    for year_index in range(3):
        year = end_year - 2 + year_index
        for month, day in ((2, 10), (5, 10), (8, 10), (11, 10)):
            records.append(
                {
                    "ticker": ticker,
                    "currency": "USD",
                    "ex_dividend_date": date(year, month, day).isoformat(),
                    "price": 0.25,
                    "last_updated": "2026-08-30T09:00:02+00:00",
                    "source": "yfinance",
                }
            )
    return records


def _fake_dividends_client_factory(
    created: list[MagicMock] | None = None, records_by_ticker: dict[str, list[dict]] | None = None
):
    def fake_dividends_client(ticker: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = ticker
        default_records = records_by_ticker.get(ticker) if records_by_ticker else None
        client.dividends.return_value = (
            default_records if default_records is not None else _quarterly_records(ticker)
        )
        if created is not None:
            created.append(client)
        return client

    return fake_dividends_client


def test_run_writes_one_forecast_file_per_ticker(tmp_path: Path) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text("tickers:\n  - AAPL\n  - MSFT\n")
    out_dir = tmp_path / "output"

    with (
        patch("equicast_forecasting.cli.DatafeedClient"),
        patch(
            "equicast_forecasting.cli.DividendsClient",
            side_effect=_fake_dividends_client_factory(),
        ),
    ):
        written = run("stock", config, out_dir)

    assert set(written) == {
        out_dir / "stock=AAPL" / "forecasting" / "dividends.parquet",
        out_dir / "stock=MSFT" / "forecasting" / "dividends.parquet",
    }


def test_run_accepts_tickers_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with (
        patch("equicast_forecasting.cli.DatafeedClient"),
        patch(
            "equicast_forecasting.cli.DividendsClient",
            side_effect=_fake_dividends_client_factory(),
        ),
    ):
        written = run("etf", None, out_dir, tickers_json='["VOO"]')

    assert written == [out_dir / "etf=VOO" / "forecasting" / "dividends.parquet"]


def test_run_writes_nothing_for_a_ticker_with_no_dependable_cadence(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    dividends_created: list[MagicMock] = []

    with (
        patch("equicast_forecasting.cli.DatafeedClient"),
        patch(
            "equicast_forecasting.cli.DividendsClient",
            side_effect=_fake_dividends_client_factory(
                dividends_created, records_by_ticker={"GLD": []}
            ),
        ),
    ):
        written = run("etf", None, out_dir, tickers_json='["GLD"]')

    assert written == []
    assert not (out_dir / "etf=GLD").exists()


def test_run_fetches_full_dividend_history_regardless_of_years(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    dividends_created: list[MagicMock] = []

    with (
        patch("equicast_forecasting.cli.DatafeedClient"),
        patch(
            "equicast_forecasting.cli.DividendsClient",
            side_effect=_fake_dividends_client_factory(dividends_created),
        ),
    ):
        run("stock", None, out_dir, tickers_json='["AAPL"]', years=1)

    assert len(dividends_created) == 1
    dividends_created[0].dividends.assert_called_once_with(full_load=True)


def test_run_shares_one_datafeed_client_across_workers(tmp_path: Path) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text("tickers:\n  - AAPL\n  - MSFT\n")
    out_dir = tmp_path / "output"

    with (
        patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls,
        patch(
            "equicast_forecasting.cli.DividendsClient",
            side_effect=_fake_dividends_client_factory(),
        ),
    ):
        run("stock", config, out_dir, max_workers=2, max_calls=5, period_seconds=2.0)

    datafeed_cls.assert_called_once_with(max_calls=5, period_seconds=2.0)
