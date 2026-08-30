from pathlib import Path

from equicast_etf.config import ETFTicker, load_etf_tickers, parse_etf_tickers_json


def test_load_etf_tickers(tmp_path: Path) -> None:
    config = tmp_path / "etfs.yaml"
    config.write_text(
        """
        tickers:
          - voo
          - qqq
        """
    )

    tickers = load_etf_tickers(config)

    assert tickers == [
        ETFTicker(ticker="VOO"),
        ETFTicker(ticker="QQQ"),
    ]


def test_etf_ticker_key() -> None:
    assert ETFTicker(ticker="VOO").key == "VOO"


def test_parse_etf_tickers_json() -> None:
    tickers = parse_etf_tickers_json('["voo", "qqq"]')

    assert tickers == [
        ETFTicker(ticker="VOO"),
        ETFTicker(ticker="QQQ"),
    ]
