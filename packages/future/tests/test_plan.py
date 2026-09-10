import json
from pathlib import Path

import pytest
from equicast_future.config import Future
from equicast_future.plan import chunk_futures


def _futures(n: int) -> list[Future]:
    return [Future(key=f"F{i:04d}", symbol=f"F{i:04d}=F") for i in range(n)]


def test_chunk_futures_respects_chunk_size_when_under_max_chunks() -> None:
    chunks = chunk_futures(_futures(10), chunk_size=4, max_chunks=256)

    assert [len(c) for c in chunks] == [4, 4, 2]


def test_chunk_futures_grows_chunk_size_to_respect_max_chunks() -> None:
    # 3000 futures at chunk_size=1 would need 3000 chunks; GitHub's matrix
    # cap forces a larger effective chunk size instead of dropping futures.
    chunks = chunk_futures(_futures(3000), chunk_size=1, max_chunks=256)

    assert len(chunks) <= 256
    assert sum(len(c) for c in chunks) == 3000


def test_chunk_futures_empty_input_returns_no_chunks() -> None:
    assert chunk_futures([], chunk_size=300, max_chunks=256) == []


def test_chunk_futures_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError):
        chunk_futures(_futures(1), chunk_size=0, max_chunks=256)
    with pytest.raises(ValueError):
        chunk_futures(_futures(1), chunk_size=1, max_chunks=0)


def test_plan_cli_prints_json_chunks(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from equicast_future.plan import main

    config = tmp_path / "futures.yaml"
    config.write_text(
        'futures:\n  - key: GOLD\n    symbol: "GC=F"\n  - key: SILVER\n    symbol: "SI=F"\n'
    )

    import sys

    old_argv = sys.argv
    sys.argv = ["equicast-future-plan", "--config", str(config), "--chunk-size", "1"]
    try:
        main()
    finally:
        sys.argv = old_argv

    output = json.loads(capsys.readouterr().out)
    assert output == [
        [{"key": "GOLD", "symbol": "GC=F"}],
        [{"key": "SILVER", "symbol": "SI=F"}],
    ]
