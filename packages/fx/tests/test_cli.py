from pathlib import Path
from unittest.mock import MagicMock, patch

from equicast_fx.cli import run


def _fake_fx_client_factory():
    def fake_fx_client(from_currency: str, to_currency: str, datafeed=None) -> MagicMock:
        client = MagicMock()
        client.profile.return_value = {
            "from_currency": from_currency,
            "to_currency": to_currency,
            "exchange": "CCY",
            "region": "US",
            "description": f"{from_currency}/{to_currency}",
            "last_updated": "2026-08-28T21:29:05+00:00",
            "source": "yfinance",
        }
        return client

    return fake_fx_client


def test_run_writes_a_parquet_file_per_configured_pair(tmp_path: Path) -> None:
    config = tmp_path / "fx_pairs.yaml"
    config.write_text("pairs:\n  - from: GBP\n    to: USD\n  - from: USD\n    to: GBP\n")
    out_dir = tmp_path / "output"

    with (
        patch("equicast_fx.cli.DatafeedClient"),
        patch("equicast_fx.cli.FXClient", side_effect=_fake_fx_client_factory()),
    ):
        written = run(config, out_dir)

    assert len(written) == 2
    assert (out_dir / "fx=GBPUSD" / "profile.parquet").exists()
    assert (out_dir / "fx=USDGBP" / "profile.parquet").exists()


def test_run_accepts_pairs_json_instead_of_config(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    pairs_json = '[{"from": "GBP", "to": "EUR"}]'

    with (
        patch("equicast_fx.cli.DatafeedClient"),
        patch("equicast_fx.cli.FXClient", side_effect=_fake_fx_client_factory()),
    ):
        written = run(None, out_dir, pairs_json=pairs_json)

    assert written == [out_dir / "fx=GBPEUR" / "profile.parquet"]


def test_run_shares_one_datafeed_client_across_workers(tmp_path: Path) -> None:
    config = tmp_path / "fx_pairs.yaml"
    config.write_text("pairs:\n  - from: GBP\n    to: USD\n  - from: USD\n    to: GBP\n")
    out_dir = tmp_path / "output"

    with (
        patch("equicast_fx.cli.DatafeedClient") as mock_datafeed_cls,
        patch("equicast_fx.cli.FXClient", side_effect=_fake_fx_client_factory()) as mock_client,
    ):
        run(config, out_dir, max_workers=2, max_calls=5, period_seconds=2.0)

    mock_datafeed_cls.assert_called_once_with(max_calls=5, period_seconds=2.0)
    shared_datafeed = mock_datafeed_cls.return_value
    for call in mock_client.call_args_list:
        assert call.kwargs["datafeed"] is shared_datafeed
