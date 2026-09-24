from pathlib import Path

from equicast_future.config import Future, load_futures, parse_futures_json


def test_load_futures(tmp_path: Path) -> None:
    config = tmp_path / "futures.yaml"
    config.write_text(
        """
        futures:
          - key: gold
            symbol: "GC=F"
          - key: silver
            symbol: "SI=F"
        """
    )

    futures = load_futures(config)

    assert futures == [
        Future(key="GOLD", symbol="GC=F"),
        Future(key="SILVER", symbol="SI=F"),
    ]


def test_parse_futures_json() -> None:
    futures = parse_futures_json(
        '[{"key": "gold", "symbol": "GC=F"}, {"key": "silver", "symbol": "SI=F"}]'
    )

    assert futures == [
        Future(key="GOLD", symbol="GC=F"),
        Future(key="SILVER", symbol="SI=F"),
    ]
