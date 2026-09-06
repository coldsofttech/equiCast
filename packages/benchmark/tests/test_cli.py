from pathlib import Path
from unittest.mock import MagicMock, patch

from equicast_benchmark.cli import run


def _fake_benchmark_client_factory(created: list[MagicMock] | None = None):
    def fake_benchmark_client(key: str, symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = symbol
        client.profile.return_value = {
            "key": key,
            "symbol": symbol,
            "name": key,
            "exchange": "SNP",
            "currency": "USD",
            "region": "US",
            "last_updated": "2026-08-28T21:29:05+00:00",
            "source": "yfinance",
        }
        client.prices.return_value = [
            {
                "key": key,
                "symbol": symbol,
                "date": "2026-01-15",
                "open": 6400.0,
                "high": 6420.0,
                "low": 6390.0,
                "close": 6410.0,
                "average": 6405.0,
                "last_updated": "2026-08-28T21:29:05+00:00",
                "source": "yfinance",
            }
        ]
        if created is not None:
            created.append(client)
        return client

    return fake_benchmark_client


def _fake_metrics_client_factory(created: list[MagicMock] | None = None):
    def fake_metrics_client(symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.metrics.return_value = {
            "volatility": 0.08,
            "sharpe_ratio": 0.4,
            "max_drawdown": -0.06,
            "cagr_1y": 0.09,
            "cagr_2y": 0.08,
            "cagr_3y": 0.07,
            "cagr_5y": 0.09,
            "cagr_10y": 0.06,
            "last_updated": "2026-08-29T12:00:00+00:00",
            "source": "equicast",
        }
        if created is not None:
            created.append(client)
        return client

    return fake_metrics_client


def _patch_clients(benchmark_created: list[MagicMock] | None = None):
    return (
        patch("equicast_benchmark.cli.DatafeedClient"),
        patch(
            "equicast_benchmark.cli.BenchmarkClient",
            side_effect=_fake_benchmark_client_factory(benchmark_created),
        ),
        patch("equicast_benchmark.cli.MetricsClient", side_effect=_fake_metrics_client_factory()),
    )


def test_run_writes_profile_price_and_metrics_parquet_per_configured_benchmark(
    tmp_path: Path,
) -> None:
    config = tmp_path / "benchmarks.yaml"
    config.write_text(
        'benchmarks:\n  - key: SP500\n    symbol: "^GSPC"\n  - key: DAX\n    symbol: "^GDAXI"\n'
    )
    out_dir = tmp_path / "output"

    datafeed_patch, benchmark_patch, metrics_patch = _patch_clients()
    with datafeed_patch, benchmark_patch, metrics_patch:
        written = run(config, out_dir)

    assert len(written) == 6  # profile + price + metrics per benchmark
    for key in ("SP500", "DAX"):
        assert (out_dir / f"benchmark={key}" / "profile.parquet").exists()
        assert (out_dir / f"benchmark={key}" / "price" / "current.parquet").exists()
        assert (out_dir / f"benchmark={key}" / "metrics.parquet").exists()


def test_run_accepts_benchmarks_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    benchmarks_json = '[{"key": "FTSE100", "symbol": "^FTSE"}]'

    datafeed_patch, benchmark_patch, metrics_patch = _patch_clients()
    with datafeed_patch, benchmark_patch, metrics_patch:
        written = run(None, out_dir, benchmarks_json=benchmarks_json)

    assert set(written) == {
        out_dir / "benchmark=FTSE100" / "profile.parquet",
        out_dir / "benchmark=FTSE100" / "price" / "current.parquet",
        out_dir / "benchmark=FTSE100" / "metrics.parquet",
    }


def test_run_passes_full_load_through_to_prices_only(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    benchmarks_json = '[{"key": "SP500", "symbol": "^GSPC"}]'
    benchmark_created: list[MagicMock] = []
    metrics_created: list[MagicMock] = []

    with (
        patch("equicast_benchmark.cli.DatafeedClient"),
        patch(
            "equicast_benchmark.cli.BenchmarkClient",
            side_effect=_fake_benchmark_client_factory(benchmark_created),
        ),
        patch(
            "equicast_benchmark.cli.MetricsClient",
            side_effect=_fake_metrics_client_factory(metrics_created),
        ),
    ):
        run(None, out_dir, benchmarks_json=benchmarks_json, full_load=True)

    # one BenchmarkClient per benchmark, shared by the profile + prices tasks
    assert len(benchmark_created) == 1
    benchmark_created[0].prices.assert_called_once_with(full_load=True)
    assert len(metrics_created) == 1
    metrics_created[0].metrics.assert_called_once_with()  # full_load doesn't affect metrics


def test_run_shares_one_datafeed_client_across_workers(tmp_path: Path) -> None:
    config = tmp_path / "benchmarks.yaml"
    config.write_text(
        'benchmarks:\n  - key: SP500\n    symbol: "^GSPC"\n  - key: DAX\n    symbol: "^GDAXI"\n'
    )
    out_dir = tmp_path / "output"

    with (
        patch("equicast_benchmark.cli.DatafeedClient") as mock_datafeed_cls,
        patch(
            "equicast_benchmark.cli.BenchmarkClient",
            side_effect=_fake_benchmark_client_factory(),
        ) as mock_client,
        patch(
            "equicast_benchmark.cli.MetricsClient", side_effect=_fake_metrics_client_factory()
        ) as mock_metrics_client,
    ):
        run(config, out_dir, max_workers=2, max_calls=5, period_seconds=2.0)

    mock_datafeed_cls.assert_called_once_with(max_calls=5, period_seconds=2.0)
    shared_datafeed = mock_datafeed_cls.return_value
    for call in mock_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
    for call in mock_metrics_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
