import json
from pathlib import Path

import pytest
from equicast_fx.config import FxPair
from equicast_fx.plan import chunk_pairs, filter_pairs


def _pairs(n: int) -> list[FxPair]:
    return [FxPair(from_currency=f"C{i:04d}", to_currency="USD") for i in range(n)]


def test_chunk_pairs_respects_chunk_size_when_under_max_chunks() -> None:
    chunks = chunk_pairs(_pairs(10), chunk_size=4, max_chunks=256)

    assert [len(c) for c in chunks] == [4, 4, 2]


def test_chunk_pairs_grows_chunk_size_to_respect_max_chunks() -> None:
    # 3000 pairs at chunk_size=1 would need 3000 chunks; GitHub's matrix cap
    # forces a larger effective chunk size instead of dropping pairs.
    chunks = chunk_pairs(_pairs(3000), chunk_size=1, max_chunks=256)

    assert len(chunks) <= 256
    assert sum(len(c) for c in chunks) == 3000


def test_chunk_pairs_empty_input_returns_no_chunks() -> None:
    assert chunk_pairs([], chunk_size=300, max_chunks=256) == []


def test_chunk_pairs_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        chunk_pairs(_pairs(1), chunk_size=0, max_chunks=256)
    with pytest.raises(ValueError):
        chunk_pairs(_pairs(1), chunk_size=1, max_chunks=0)


def test_filter_pairs_returns_unchanged_when_keys_is_none() -> None:
    pairs = _pairs(3)
    assert filter_pairs(pairs, None) == pairs


def test_filter_pairs_restricts_to_matching_keys() -> None:
    pairs = [
        FxPair(from_currency="GBP", to_currency="USD"),
        FxPair(from_currency="EUR", to_currency="USD"),
    ]

    assert [p.key for p in filter_pairs(pairs, "EURUSD")] == ["EURUSD"]


def test_filter_pairs_is_case_insensitive_and_ignores_blank_entries() -> None:
    pairs = [
        FxPair(from_currency="GBP", to_currency="USD"),
        FxPair(from_currency="EUR", to_currency="USD"),
    ]

    assert [p.key for p in filter_pairs(pairs, " gbpusd ; ;eurusd ")] == ["GBPUSD", "EURUSD"]


def test_plan_cli_prints_json_chunks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from equicast_fx.plan import main

    config = tmp_path / "fx_pairs.yaml"
    config.write_text("pairs:\n  - from: GBP\n    to: USD\n  - from: USD\n    to: GBP\n")

    import sys

    old_argv = sys.argv
    sys.argv = ["equicast-fx-plan", "--config", str(config), "--chunk-size", "1"]
    try:
        main()
    finally:
        sys.argv = old_argv

    output = json.loads(capsys.readouterr().out)
    assert output == [
        [{"from": "GBP", "to": "USD"}],
        [{"from": "USD", "to": "GBP"}],
    ]


def test_plan_cli_restricts_to_given_tickers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from equicast_fx.plan import main

    config = tmp_path / "fx_pairs.yaml"
    config.write_text(
        "pairs:\n"
        "  - from: GBP\n    to: USD\n"
        "  - from: USD\n    to: GBP\n"
        "  - from: EUR\n    to: USD\n"
    )

    import sys

    old_argv = sys.argv
    sys.argv = [
        "equicast-fx-plan",
        "--config",
        str(config),
        "--chunk-size",
        "300",
        "--tickers",
        "GBPUSD;EURUSD",
    ]
    try:
        main()
    finally:
        sys.argv = old_argv

    output = json.loads(capsys.readouterr().out)
    assert output == [
        [{"from": "GBP", "to": "USD"}, {"from": "EUR", "to": "USD"}],
    ]
