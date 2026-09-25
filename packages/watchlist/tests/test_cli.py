import json
from pathlib import Path
from unittest.mock import patch

from equicast_watchlist.cli import run


def _fake_built_entries(entries, datafeed, max_workers=1):
    built = [
        {
            "asset_class": entry.asset_class,
            "ticker": entry.ticker,
            "symbol": entry.symbol or f"{entry.from_currency}{entry.to_currency}=X",
            "name": entry.name,
            "currency": "USD",
            "current_price": 1.0,
            "change_1w_pct": 0.1,
            "change_1m_pct": 0.2,
            "last_updated": "2026-08-28T21:29:05+00:00",
            "source": "yfinance",
        }
        for entry in entries
    ]
    return built, []


def test_run_writes_one_parquet_file_for_the_configured_watchlist(tmp_path: Path) -> None:
    config = tmp_path / "watchlist.yaml"
    config.write_text(
        """
        entries:
          - asset_class: future
            key: gold
            symbol: "GC=F"
            name: Gold
          - asset_class: fx
            from: eur
            to: usd
            name: EUR/USD
        """
    )
    out_dir = tmp_path / "output"

    with (
        patch("equicast_watchlist.cli.DatafeedClient") as mock_datafeed_cls,
        patch(
            "equicast_watchlist.cli.build_entries", side_effect=_fake_built_entries
        ) as mock_build,
    ):
        path = run("GLOBAL_MARKETS", config, out_dir)

    assert path == out_dir / "watchlist=GLOBAL_MARKETS" / "entries.parquet"
    assert path.exists()
    mock_datafeed_cls.assert_called_once_with(max_calls=1, period_seconds=1.0)
    assert mock_build.call_count == 1


def test_run_passes_max_workers_and_rate_limit_through(tmp_path: Path) -> None:
    config = tmp_path / "watchlist.yaml"
    config.write_text(
        'entries:\n  - asset_class: future\n    key: gold\n    symbol: "GC=F"\n    name: Gold\n'
    )
    out_dir = tmp_path / "output"

    with (
        patch("equicast_watchlist.cli.DatafeedClient") as mock_datafeed_cls,
        patch(
            "equicast_watchlist.cli.build_entries", side_effect=_fake_built_entries
        ) as mock_build,
    ):
        run(
            "GLOBAL_MARKETS",
            config,
            out_dir,
            max_workers=5,
            max_calls=10,
            period_seconds=2.0,
        )

    mock_datafeed_cls.assert_called_once_with(max_calls=10, period_seconds=2.0)
    assert mock_build.call_args.kwargs["max_workers"] == 5


def test_run_writes_a_failures_manifest_when_build_entries_reports_failures(
    tmp_path: Path,
) -> None:
    config = tmp_path / "watchlist.yaml"
    config.write_text(
        'entries:\n  - asset_class: future\n    key: gold\n    symbol: "GC=F"\n    name: Gold\n'
    )
    out_dir = tmp_path / "output"
    failures = [{"ticker": "GOLD", "task": "profile", "error": "yfinance boom"}]

    def fake_built_entries_with_failure(entries, datafeed, max_workers=1):
        return [], failures

    with (
        patch("equicast_watchlist.cli.DatafeedClient"),
        patch(
            "equicast_watchlist.cli.build_entries",
            side_effect=fake_built_entries_with_failure,
        ),
    ):
        run("GLOBAL_MARKETS", config, out_dir)

    written_failures = json.loads((out_dir / "failures.json").read_text(encoding="utf-8"))
    assert written_failures == failures


def test_run_writes_no_failures_manifest_when_every_entry_succeeds(tmp_path: Path) -> None:
    config = tmp_path / "watchlist.yaml"
    config.write_text(
        'entries:\n  - asset_class: future\n    key: gold\n    symbol: "GC=F"\n    name: Gold\n'
    )
    out_dir = tmp_path / "output"

    with (
        patch("equicast_watchlist.cli.DatafeedClient"),
        patch("equicast_watchlist.cli.build_entries", side_effect=_fake_built_entries),
    ):
        run("GLOBAL_MARKETS", config, out_dir)

    assert not (out_dir / "failures.json").exists()
