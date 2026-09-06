from pathlib import Path

from equicast_forecasting.config import load_tickers, parse_tickers_json


def test_load_tickers(tmp_path: Path) -> None:
    config = tmp_path / "stocks.yaml"
    config.write_text(
        """
        tickers:
          - aapl
          - msft
        """
    )

    assert load_tickers(config) == ["AAPL", "MSFT"]


def test_parse_tickers_json() -> None:
    assert parse_tickers_json('["aapl", "msft"]') == ["AAPL", "MSFT"]
