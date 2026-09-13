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


def test_load_etf_tickers_with_isin_and_tax_domicile_overrides(tmp_path: Path) -> None:
    config = tmp_path / "etfs.yaml"
    config.write_text(
        """
        tickers:
          - voo
          - ticker: iwda
            isin: IE00B4L5Y983
          - ticker: qqq
            isin: US46090E1038
            tax_domicile: US
        """
    )

    tickers = load_etf_tickers(config)

    assert tickers == [
        ETFTicker(ticker="VOO"),
        ETFTicker(ticker="IWDA", isin="IE00B4L5Y983"),
        ETFTicker(ticker="QQQ", isin="US46090E1038", tax_domicile="US"),
    ]


def test_etf_ticker_key() -> None:
    assert ETFTicker(ticker="VOO").key == "VOO"


def test_parse_etf_tickers_json() -> None:
    tickers = parse_etf_tickers_json('["voo", "qqq"]')

    assert tickers == [
        ETFTicker(ticker="VOO"),
        ETFTicker(ticker="QQQ"),
    ]


def test_parse_etf_tickers_json_with_isin_and_tax_domicile_overrides() -> None:
    tickers = parse_etf_tickers_json(
        '[{"ticker": "qqq", "isin": "US46090E1038", "tax_domicile": "US"}]'
    )

    assert tickers == [ETFTicker(ticker="QQQ", isin="US46090E1038", tax_domicile="US")]
