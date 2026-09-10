from pathlib import Path
from unittest.mock import MagicMock, patch

from equicast_future.cli import run


def _fake_future_client_factory(created: list[MagicMock] | None = None):
    def fake_future_client(key: str, symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.symbol = symbol
        client.profile.return_value = {
            "key": key,
            "symbol": symbol,
            "name": key,
            "exchange": "CMX",
            "currency": "USD",
            "region": None,
            "last_updated": "2026-08-28T21:29:05+00:00",
            "source": "yfinance",
        }
        client.prices.return_value = [
            {
                "key": key,
                "symbol": symbol,
                "date": "2026-01-15",
                "open": 2400.0,
                "high": 2420.0,
                "low": 2390.0,
                "close": 2410.0,
                "average": 2405.0,
                "last_updated": "2026-08-28T21:29:05+00:00",
                "source": "yfinance",
            }
        ]
        if created is not None:
            created.append(client)
        return client

    return fake_future_client


def _fake_metrics_client_factory(created: list[MagicMock] | None = None):
    def fake_metrics_client(symbol: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.metrics.return_value = {
            "volatility": 0.19,
            "sharpe_ratio": 0.31,
            "max_drawdown": -0.14,
            "cagr_1y": 0.12,
            "cagr_2y": 0.1,
            "cagr_3y": 0.09,
            "cagr_5y": 0.08,
            "cagr_10y": 0.06,
            "last_updated": "2026-08-29T12:00:00+00:00",
            "source": "equicast",
        }
        if created is not None:
            created.append(client)
        return client

    return fake_metrics_client


def _patch_clients(future_created: list[MagicMock] | None = None):
    return (
        patch("equicast_future.cli.DatafeedClient"),
        patch(
            "equicast_future.cli.FutureClient",
            side_effect=_fake_future_client_factory(future_created),
        ),
        patch("equicast_future.cli.MetricsClient", side_effect=_fake_metrics_client_factory()),
    )


def test_run_writes_profile_price_and_metrics_parquet_per_configured_future(
    tmp_path: Path,
) -> None:
    config = tmp_path / "futures.yaml"
    config.write_text(
        'futures:\n  - key: GOLD\n    symbol: "GC=F"\n  - key: SILVER\n    symbol: "SI=F"\n'
    )
    out_dir = tmp_path / "output"

    datafeed_patch, future_patch, metrics_patch = _patch_clients()
    with datafeed_patch, future_patch, metrics_patch:
        written = run(config, out_dir)

    assert len(written) == 6  # profile + price + metrics per future
    for key in ("GOLD", "SILVER"):
        assert (out_dir / f"future={key}" / "profile.parquet").exists()
        assert (out_dir / f"future={key}" / "price" / "current.parquet").exists()
        assert (out_dir / f"future={key}" / "metrics.parquet").exists()


def test_run_accepts_futures_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    futures_json = '[{"key": "PLATINUM", "symbol": "PL=F"}]'

    datafeed_patch, future_patch, metrics_patch = _patch_clients()
    with datafeed_patch, future_patch, metrics_patch:
        written = run(None, out_dir, futures_json=futures_json)

    assert set(written) == {
        out_dir / "future=PLATINUM" / "profile.parquet",
        out_dir / "future=PLATINUM" / "price" / "current.parquet",
        out_dir / "future=PLATINUM" / "metrics.parquet",
    }


def test_run_passes_full_load_through_to_prices_only(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    futures_json = '[{"key": "GOLD", "symbol": "GC=F"}]'
    future_created: list[MagicMock] = []
    metrics_created: list[MagicMock] = []

    with (
        patch("equicast_future.cli.DatafeedClient"),
        patch(
            "equicast_future.cli.FutureClient",
            side_effect=_fake_future_client_factory(future_created),
        ),
        patch(
            "equicast_future.cli.MetricsClient",
            side_effect=_fake_metrics_client_factory(metrics_created),
        ),
    ):
        run(None, out_dir, futures_json=futures_json, full_load=True)

    # one FutureClient per future, shared by the profile + prices tasks
    assert len(future_created) == 1
    future_created[0].prices.assert_called_once_with(full_load=True)
    assert len(metrics_created) == 1
    metrics_created[0].metrics.assert_called_once_with()  # full_load doesn't affect metrics


def test_run_shares_one_datafeed_client_across_workers(tmp_path: Path) -> None:
    config = tmp_path / "futures.yaml"
    config.write_text(
        'futures:\n  - key: GOLD\n    symbol: "GC=F"\n  - key: SILVER\n    symbol: "SI=F"\n'
    )
    out_dir = tmp_path / "output"

    with (
        patch("equicast_future.cli.DatafeedClient") as mock_datafeed_cls,
        patch(
            "equicast_future.cli.FutureClient",
            side_effect=_fake_future_client_factory(),
        ) as mock_client,
        patch(
            "equicast_future.cli.MetricsClient", side_effect=_fake_metrics_client_factory()
        ) as mock_metrics_client,
    ):
        run(config, out_dir, max_workers=2, max_calls=5, period_seconds=2.0)

    mock_datafeed_cls.assert_called_once_with(max_calls=5, period_seconds=2.0)
    shared_datafeed = mock_datafeed_cls.return_value
    for call in mock_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
    for call in mock_metrics_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
