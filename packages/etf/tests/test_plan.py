import json
from pathlib import Path

import pytest
from equicast_etf.config import ETFTicker
from equicast_etf.plan import chunk_tickers


def _tickers(n: int) -> list[ETFTicker]:
    return [ETFTicker(ticker=f"T{i:04d}") for i in range(n)]


def test_chunk_tickers_respects_chunk_size_when_under_max_chunks() -> None:
    chunks = chunk_tickers(_tickers(10), chunk_size=4, max_chunks=256)

    assert [len(c) for c in chunks] == [4, 4, 2]


def test_chunk_tickers_grows_chunk_size_to_respect_max_chunks() -> None:
    # 3000 tickers at chunk_size=1 would need 3000 chunks; GitHub's matrix
    # cap forces a larger effective chunk size instead of dropping tickers.
    chunks = chunk_tickers(_tickers(3000), chunk_size=1, max_chunks=256)

    assert len(chunks) <= 256
    assert sum(len(c) for c in chunks) == 3000


def test_chunk_tickers_empty_input_returns_no_chunks() -> None:
    assert chunk_tickers([], chunk_size=300, max_chunks=256) == []


def test_chunk_tickers_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        chunk_tickers(_tickers(1), chunk_size=0, max_chunks=256)
    with pytest.raises(ValueError):
        chunk_tickers(_tickers(1), chunk_size=1, max_chunks=0)


def test_plan_cli_prints_json_chunks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from equicast_etf.plan import main

    config = tmp_path / "etfs.yaml"
    config.write_text("tickers:\n  - VOO\n  - QQQ\n")

    import sys

    old_argv = sys.argv
    sys.argv = ["equicast-etf-plan", "--config", str(config), "--chunk-size", "1"]
    try:
        main()
    finally:
        sys.argv = old_argv

    output = json.loads(capsys.readouterr().out)
    assert output == [["VOO"], ["QQQ"]]
