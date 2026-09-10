from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from equicast_forecasting.benchmark_registry import UnroutableBenchmarkError
from equicast_forecasting.cli import ForecastBatchError, run
from equicast_forecasting.commodity_registry import UnroutableCommodityError
from equicast_forecasting.etf_type_registry import UnroutableEtfTypeError
from equicast_forecasting.sector_registry import UnroutableSectorError


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
        written = run("stock", "dividends", config, out_dir)

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
        written = run("etf", "dividends", None, out_dir, tickers_json='["VOO"]')

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
        written = run("etf", "dividends", None, out_dir, tickers_json='["GLD"]')

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
        run("stock", "dividends", None, out_dir, tickers_json='["AAPL"]', years=1)

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
        run("stock", "dividends", config, out_dir, max_workers=2, max_calls=5, period_seconds=2.0)

    datafeed_cls.assert_called_once_with(max_calls=5, period_seconds=2.0)


def _fx_history(num_days: int = 30, start: float = 1.30) -> pd.DataFrame:
    dates = pd.date_range(end=pd.Timestamp.today(), periods=num_days, freq="D")
    closes = [start + 0.001 * i for i in range(num_days)]
    return pd.DataFrame({"Close": closes}, index=dates)


def _fake_get_history(price_by_symbol: dict[str, pd.DataFrame]):
    def get_history(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        return price_by_symbol.get(symbol, pd.DataFrame())

    return get_history


def test_run_writes_fx_price_bands_per_pair(tmp_path: Path) -> None:
    config = tmp_path / "fx_pairs.yaml"
    config.write_text("pairs:\n  - from: GBP\n    to: USD\n  - from: EUR\n    to: GBP\n")
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"GBPUSD=X": _fx_history(), "EURGBP=X": _fx_history(start=0.85)}
        )
        written = run("fx", "price-bands", config, out_dir, years=1)

    assert set(written) == {
        out_dir / "fx=GBPUSD" / "forecasting" / "price_bands.parquet",
        out_dir / "fx=EURGBP" / "forecasting" / "price_bands.parquet",
    }


def test_run_accepts_pairs_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"GBPUSD=X": _fx_history()}
        )
        written = run(
            "fx", "price-bands", None, out_dir, pairs_json='[{"from": "gbp", "to": "usd"}]', years=1
        )

    assert written == [out_dir / "fx=GBPUSD" / "forecasting" / "price_bands.parquet"]


def test_run_writes_nothing_for_a_pair_with_insufficient_price_history(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"GBPUSD=X": _fx_history(num_days=1)}
        )
        written = run(
            "fx", "price-bands", None, out_dir, pairs_json='[{"from": "gbp", "to": "usd"}]', years=1
        )

    assert written == []
    assert not (out_dir / "fx=GBPUSD").exists()


def test_run_rejects_tickers_json_with_fx_asset_class(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--tickers-json is stock/etf only"):
        run("fx", "price-bands", None, tmp_path / "out", tickers_json='["AAPL"]')


def test_run_rejects_pairs_json_with_non_fx_asset_class(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--pairs-json is fx only"):
        run(
            "stock",
            "dividends",
            None,
            tmp_path / "out",
            pairs_json='[{"from": "gbp", "to": "usd"}]',
        )


def test_run_rejects_dividends_forecast_kind_for_fx(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--forecast-kind dividends is stock/etf only"):
        run("fx", "dividends", None, tmp_path / "out", pairs_json='[{"from": "gbp", "to": "usd"}]')


def test_run_rejects_price_bands_forecast_kind_for_unsupported_asset_class(tmp_path: Path) -> None:
    # "stock"/"etf"/"fx"/"benchmark"/"future" are the only five
    # --asset-class choices argparse itself allows, and price-bands now
    # supports all five (issue #67 added etf, issue #68 added benchmark,
    # issue #143 added future) - so this exercises _validate_forecast_
    # kind's own guard directly with a class outside that set, rather than
    # a real CLI input.
    with pytest.raises(
        ValueError, match="--forecast-kind price-bands is stock/etf/fx/benchmark/future only"
    ):
        run("crypto", "price-bands", None, tmp_path / "out", tickers_json='["VOO"]')


def test_run_rejects_benchmarks_json_with_non_benchmark_asset_class(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--benchmarks-json is benchmark only"):
        run(
            "stock",
            "dividends",
            None,
            tmp_path / "out",
            benchmarks_json='[{"key": "SP500", "symbol": "^GSPC"}]',
        )


def test_run_rejects_futures_json_with_non_future_asset_class(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--futures-json is future only"):
        run(
            "stock",
            "dividends",
            None,
            tmp_path / "out",
            futures_json='[{"key": "GOLD", "symbol": "GC=F"}]',
        )


def test_run_shares_one_datafeed_client_across_fx_workers(tmp_path: Path) -> None:
    config = tmp_path / "fx_pairs.yaml"
    config.write_text("pairs:\n  - from: GBP\n    to: USD\n  - from: EUR\n    to: GBP\n")
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"GBPUSD=X": _fx_history(), "EURGBP=X": _fx_history(start=0.85)}
        )
        run("fx", "price-bands", config, out_dir, max_workers=2, max_calls=5, period_seconds=2.0)

    datafeed_cls.assert_called_once_with(max_calls=5, period_seconds=2.0)


def _stock_history(num_days: int = 300, start: float = 100.0) -> pd.DataFrame:
    dates = pd.date_range(end=pd.Timestamp.today(), periods=num_days, freq="D")
    closes = [start + 0.01 * i for i in range(num_days)]
    return pd.DataFrame({"Close": closes}, index=dates)


def _fake_get_info(info_by_ticker: dict[str, dict]):
    def get_info(ticker: str) -> dict:
        return info_by_ticker.get(ticker, {})

    return get_info


def _patch_stock_forecast(datafeed_cls, info_by_ticker, history_by_ticker):
    datafeed_cls.return_value.get_info.side_effect = _fake_get_info(info_by_ticker)
    datafeed_cls.return_value.get_history.side_effect = _fake_get_history(history_by_ticker)
    datafeed_cls.return_value.get_financials.return_value = pd.DataFrame()
    datafeed_cls.return_value.get_balance_sheet.return_value = pd.DataFrame()


def test_run_writes_stock_price_bands_per_ticker(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        _patch_stock_forecast(
            datafeed_cls,
            {"AAPL": {"sector": "Technology", "industry": "Semiconductors"}},
            {"AAPL": _stock_history()},
        )
        written = run(
            "stock", "price-bands", None, out_dir, tickers_json='["AAPL"]', years=1, num_paths=50
        )

    assert written == [out_dir / "stock=AAPL" / "forecasting" / "price_bands.parquet"]


def test_run_raises_forecast_batch_error_for_unroutable_ticker(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        _patch_stock_forecast(
            datafeed_cls,
            {"ZZZZ": {"sector": "Not A Real Sector", "industry": "Whatever"}},
            {"ZZZZ": _stock_history()},
        )
        with pytest.raises(ForecastBatchError, match="ZZZZ"):
            run(
                "stock",
                "price-bands",
                None,
                out_dir,
                tickers_json='["ZZZZ"]',
                years=1,
                num_paths=50,
            )


def test_run_still_writes_routable_tickers_when_another_fails_to_route(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        _patch_stock_forecast(
            datafeed_cls,
            {
                "AAPL": {"sector": "Technology", "industry": "Semiconductors"},
                "ZZZZ": {"sector": "Not A Real Sector", "industry": "Whatever"},
            },
            {"AAPL": _stock_history(), "ZZZZ": _stock_history()},
        )
        with pytest.raises(ForecastBatchError):
            run(
                "stock",
                "price-bands",
                None,
                out_dir,
                tickers_json='["AAPL", "ZZZZ"]',
                years=1,
                num_paths=50,
            )

    # The ForecastBatchError is raised only after every ticker has run - AAPL's
    # file is written to disk regardless of ZZZZ's routing failure.
    assert (out_dir / "stock=AAPL" / "forecasting" / "price_bands.parquet").exists()
    assert not (out_dir / "stock=ZZZZ").exists()


def test_stock_forecast_task_raises_unroutable_sector_error_is_caught(tmp_path: Path) -> None:
    from equicast_forecasting.cli import _stock_forecast_task

    datafeed = MagicMock()
    datafeed.get_info.return_value = {"sector": "Not A Real Sector", "industry": "Whatever"}
    datafeed.get_history.return_value = _stock_history()
    failures: list[tuple[str, UnroutableSectorError]] = []

    result = _stock_forecast_task("ZZZZ", datafeed, tmp_path, 1, 50, failures)

    assert result is None
    assert len(failures) == 1
    assert failures[0][0] == "ZZZZ"


def _patch_etf_forecast(datafeed_cls, info_by_ticker, history_by_ticker):
    datafeed_cls.return_value.get_info.side_effect = _fake_get_info(info_by_ticker)
    datafeed_cls.return_value.get_history.side_effect = _fake_get_history(history_by_ticker)


def test_run_writes_etf_price_bands_per_ticker(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        _patch_etf_forecast(
            datafeed_cls,
            {"VOO": {"category": "Large Blend"}},
            {"VOO": _stock_history()},
        )
        written = run(
            "etf", "price-bands", None, out_dir, tickers_json='["VOO"]', years=1, num_paths=50
        )

    assert written == [out_dir / "etf=VOO" / "forecasting" / "price_bands.parquet"]


def test_run_raises_forecast_batch_error_for_unroutable_etf_category(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        _patch_etf_forecast(
            datafeed_cls,
            {"ZZZZ": {"category": "Not A Real Category"}},
            {"ZZZZ": _stock_history()},
        )
        with pytest.raises(ForecastBatchError, match="ZZZZ"):
            run(
                "etf",
                "price-bands",
                None,
                out_dir,
                tickers_json='["ZZZZ"]',
                years=1,
                num_paths=50,
            )


def test_run_still_writes_routable_etfs_when_another_fails_to_route(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        _patch_etf_forecast(
            datafeed_cls,
            {
                "VOO": {"category": "Large Blend"},
                "ZZZZ": {"category": "Not A Real Category"},
            },
            {"VOO": _stock_history(), "ZZZZ": _stock_history()},
        )
        with pytest.raises(ForecastBatchError):
            run(
                "etf",
                "price-bands",
                None,
                out_dir,
                tickers_json='["VOO", "ZZZZ"]',
                years=1,
                num_paths=50,
            )

    # The ForecastBatchError is raised only after every ticker has run - VOO's
    # file is written to disk regardless of ZZZZ's routing failure.
    assert (out_dir / "etf=VOO" / "forecasting" / "price_bands.parquet").exists()
    assert not (out_dir / "etf=ZZZZ").exists()


def test_etf_forecast_task_raises_unroutable_etf_type_error_is_caught(tmp_path: Path) -> None:
    from equicast_forecasting.cli import _etf_forecast_task

    datafeed = MagicMock()
    datafeed.get_info.return_value = {"category": "Not A Real Category"}
    datafeed.get_history.return_value = _stock_history()
    failures: list[tuple[str, UnroutableEtfTypeError]] = []

    result = _etf_forecast_task("ZZZZ", datafeed, tmp_path, 1, 50, failures)

    assert result is None
    assert len(failures) == 1
    assert failures[0][0] == "ZZZZ"


def test_run_writes_benchmark_price_bands_per_key(tmp_path: Path) -> None:
    config = tmp_path / "benchmarks.yaml"
    config.write_text(
        'benchmarks:\n  - key: SP500\n    symbol: "^GSPC"\n  - key: FTSE100\n    symbol: "^FTSE"\n'
    )
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"^GSPC": _stock_history(), "^FTSE": _stock_history(start=7000.0)}
        )
        written = run("benchmark", "price-bands", config, out_dir, years=1, num_paths=50)

    assert set(written) == {
        out_dir / "benchmark=SP500" / "forecasting" / "price_bands.parquet",
        out_dir / "benchmark=FTSE100" / "forecasting" / "price_bands.parquet",
    }


def test_run_accepts_benchmarks_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"^GSPC": _stock_history()}
        )
        written = run(
            "benchmark",
            "price-bands",
            None,
            out_dir,
            benchmarks_json='[{"key": "sp500", "symbol": "^GSPC"}]',
            years=1,
            num_paths=50,
        )

    assert written == [out_dir / "benchmark=SP500" / "forecasting" / "price_bands.parquet"]


def test_run_raises_forecast_batch_error_for_unroutable_benchmark_key(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"^ZZZZ": _stock_history()}
        )
        with pytest.raises(ForecastBatchError, match="NOT_A_REAL_BENCHMARK"):
            run(
                "benchmark",
                "price-bands",
                None,
                out_dir,
                benchmarks_json='[{"key": "not_a_real_benchmark", "symbol": "^ZZZZ"}]',
                years=1,
                num_paths=50,
            )


def test_run_still_writes_routable_benchmarks_when_another_fails_to_route(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"^GSPC": _stock_history(), "^ZZZZ": _stock_history()}
        )
        with pytest.raises(ForecastBatchError):
            run(
                "benchmark",
                "price-bands",
                None,
                out_dir,
                benchmarks_json=(
                    '[{"key": "sp500", "symbol": "^GSPC"}, '
                    '{"key": "not_a_real_benchmark", "symbol": "^ZZZZ"}]'
                ),
                years=1,
                num_paths=50,
            )

    # The ForecastBatchError is raised only after every benchmark has run -
    # SP500's file is written to disk regardless of the other's routing failure.
    assert (out_dir / "benchmark=SP500" / "forecasting" / "price_bands.parquet").exists()
    assert not (out_dir / "benchmark=NOT_A_REAL_BENCHMARK").exists()


def test_benchmark_forecast_task_raises_unroutable_benchmark_error_is_caught(
    tmp_path: Path,
) -> None:
    from equicast_forecasting.cli import _benchmark_forecast_task
    from equicast_forecasting.config import BenchmarkRef

    datafeed = MagicMock()
    datafeed.get_history.return_value = _stock_history()
    failures: list[tuple[str, UnroutableBenchmarkError]] = []
    benchmark = BenchmarkRef(key="NOT_A_REAL_BENCHMARK", symbol="^ZZZZ")

    result = _benchmark_forecast_task(benchmark, datafeed, tmp_path, 1, 50, failures)

    assert result is None
    assert len(failures) == 1
    assert failures[0][0] == "NOT_A_REAL_BENCHMARK"


def test_run_writes_future_price_bands_per_key(tmp_path: Path) -> None:
    config = tmp_path / "futures.yaml"
    config.write_text(
        'futures:\n  - key: GOLD\n    symbol: "GC=F"\n  - key: WHEAT\n    symbol: "ZW=F"\n'
    )
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"GC=F": _stock_history(), "ZW=F": _stock_history(start=600.0)}
        )
        written = run("future", "price-bands", config, out_dir, years=1, num_paths=50)

    assert set(written) == {
        out_dir / "future=GOLD" / "forecasting" / "price_bands.parquet",
        out_dir / "future=WHEAT" / "forecasting" / "price_bands.parquet",
    }


def test_run_accepts_futures_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"GC=F": _stock_history()}
        )
        written = run(
            "future",
            "price-bands",
            None,
            out_dir,
            futures_json='[{"key": "gold", "symbol": "GC=F"}]',
            years=1,
            num_paths=50,
        )

    assert written == [out_dir / "future=GOLD" / "forecasting" / "price_bands.parquet"]


def test_run_raises_forecast_batch_error_for_unroutable_future_key(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"ZZ=F": _stock_history()}
        )
        with pytest.raises(ForecastBatchError, match="NOT_A_REAL_FUTURE"):
            run(
                "future",
                "price-bands",
                None,
                out_dir,
                futures_json='[{"key": "not_a_real_future", "symbol": "ZZ=F"}]',
                years=1,
                num_paths=50,
            )


def test_run_still_writes_routable_futures_when_another_fails_to_route(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"

    with patch("equicast_forecasting.cli.DatafeedClient") as datafeed_cls:
        datafeed_cls.return_value.get_history.side_effect = _fake_get_history(
            {"GC=F": _stock_history(), "ZZ=F": _stock_history()}
        )
        with pytest.raises(ForecastBatchError):
            run(
                "future",
                "price-bands",
                None,
                out_dir,
                futures_json=(
                    '[{"key": "gold", "symbol": "GC=F"}, '
                    '{"key": "not_a_real_future", "symbol": "ZZ=F"}]'
                ),
                years=1,
                num_paths=50,
            )

    # The ForecastBatchError is raised only after every future has run -
    # GOLD's file is written to disk regardless of the other's routing failure.
    assert (out_dir / "future=GOLD" / "forecasting" / "price_bands.parquet").exists()
    assert not (out_dir / "future=NOT_A_REAL_FUTURE").exists()


def test_future_forecast_task_raises_unroutable_commodity_error_is_caught(
    tmp_path: Path,
) -> None:
    from equicast_forecasting.cli import _future_forecast_task
    from equicast_forecasting.config import FutureRef

    datafeed = MagicMock()
    datafeed.get_history.return_value = _stock_history()
    failures: list[tuple[str, UnroutableCommodityError]] = []
    future_ref = FutureRef(key="NOT_A_REAL_FUTURE", symbol="ZZ=F")

    result = _future_forecast_task(future_ref, datafeed, tmp_path, 1, 50, failures)

    assert result is None
    assert len(failures) == 1
    assert failures[0][0] == "NOT_A_REAL_FUTURE"
