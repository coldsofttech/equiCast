import io

import pytest
from equicast_core.imports import (
    PRESETS,
    ImportParseError,
    ParsedRow,
    parse_generic_csv,
    parse_trading212_csv,
)


def _csv(text: str) -> io.StringIO:
    return io.StringIO(text.strip("\n") + "\n")


TRADING212_HEADER = (
    "Action,Time (UTC),ISIN,Ticker,Name,ID,No. of shares,Price / share,"
    "Currency (Price / share),Exchange rate,Result,Currency (Result),Total,"
    "Currency (Total),Stamp duty reserve tax,Currency (Stamp duty reserve tax),"
    "Currency conversion fee,Currency (Currency conversion fee)"
)


class TestParseTrading212Csv:
    def test_parses_buy_and_sell_rows(self) -> None:
        file = _csv(
            f"""
            {TRADING212_HEADER}
            Market buy,2024-03-01 14:32:10,US0378331005,AAPL,Apple Inc.,EOF123,10,148.0,USD,0.79,,USD,1480.00,USD,,,,
            Market sell,2024-04-02 09:01:00,US0378331005,AAPL,Apple Inc.,EOF124,4,160.5,USD,0.80,,USD,642.00,USD,,,,
            """.replace("            ", "")
        )

        result = parse_trading212_csv(file)

        assert result.rows_skipped == 0
        assert [row.type for row in result.rows] == ["BUY", "SELL"]
        buy = result.rows[0]
        assert buy == ParsedRow(
            external_id="EOF123",
            date="2024-03-01",
            type="BUY",
            ticker="AAPL",
            asset_class=None,
            isin="US0378331005",
            name="Apple Inc.",
            no_of_shares=10.0,
            price_native=148.0,
            currency="USD",
            fx_rate=0.79,
            raw=buy.raw,
        )

    def test_drops_dividend_and_other_non_trade_rows(self) -> None:
        file = _csv(
            f"""
            {TRADING212_HEADER}
            Market buy,2024-03-01 14:32:10,US0378331005,AAPL,Apple Inc.,EOF123,10,148.0,USD,0.79,,USD,1480.00,USD,,,,
            Dividend (Dividend),2024-03-15 00:00:00,US0378331005,AAPL,Apple Inc.,EOF200,,,USD,,,USD,4.20,USD,,,,
            Interest on cash,2024-03-20 00:00:00,,,,EOF201,,,,,,,0.05,GBP,,,,
            """.replace("            ", "")
        )

        result = parse_trading212_csv(file)

        assert len(result.rows) == 1
        assert result.rows[0].type == "BUY"
        assert result.rows_skipped == 2

    def test_ignores_stamp_duty_and_conversion_fee_columns(self) -> None:
        """These columns exist in a real export but aren't modeled
        anywhere in equicast's transaction shape — parsing must not choke
        on their presence, and nothing in `ParsedRow` surfaces them."""
        file = _csv(
            f"""
            {TRADING212_HEADER}
            Market buy,2024-03-01 14:32:10,GB0002634946,BATS,British American Tobacco,EOF300,5,25.0,GBP,1.0,,GBP,125.00,GBP,0.63,GBP,0.15,GBP
            """.replace("            ", "")
        )

        result = parse_trading212_csv(file)

        assert len(result.rows) == 1
        assert not hasattr(result.rows[0], "stamp_duty_reserve_tax")

    def test_raises_import_parse_error_for_missing_required_columns(self) -> None:
        file = _csv("Action,Ticker\nMarket buy,AAPL\n")

        with pytest.raises(ImportParseError, match="Time \\(UTC\\)"):
            parse_trading212_csv(file)

    def test_raises_import_parse_error_for_non_positive_shares(self) -> None:
        file = _csv(
            f"""
            {TRADING212_HEADER}
            Market buy,2024-03-01 14:32:10,US0378331005,AAPL,Apple Inc.,EOF123,0,148.0,USD,0.79,,USD,0.00,USD,,,,
            """.replace("            ", "")
        )

        with pytest.raises(ImportParseError, match="No. of shares"):
            parse_trading212_csv(file)

    def test_exchange_rate_is_none_when_blank(self) -> None:
        file = _csv(
            f"""
            {TRADING212_HEADER}
            Market buy,2024-03-01 14:32:10,US0378331005,AAPL,Apple Inc.,EOF123,10,148.0,USD,,,USD,1480.00,USD,,,,
            """.replace("            ", "")
        )

        result = parse_trading212_csv(file)

        assert result.rows[0].fx_rate is None


class TestParseGenericCsv:
    def test_parses_required_and_optional_columns(self) -> None:
        file = _csv(
            """
            date,ticker,asset_class,type,no_of_shares,price_native,currency,fx_rate,external_id
            2024-01-10,VOD,stock,BUY,100,1.2,GBP,,manual-1
            """.replace("            ", "")
        )

        result = parse_generic_csv(file)

        assert result.rows_skipped == 0
        assert result.rows[0] == ParsedRow(
            external_id="manual-1",
            date="2024-01-10",
            type="BUY",
            ticker="VOD",
            asset_class="stock",
            isin=None,
            name=None,
            no_of_shares=100.0,
            price_native=1.2,
            currency="GBP",
            fx_rate=None,
            raw=result.rows[0].raw,
        )

    def test_works_without_optional_columns(self) -> None:
        file = _csv(
            """
            date,ticker,type,no_of_shares,price_native
            2024-01-10,VOD,SELL,50,1.3
            """.replace("            ", "")
        )

        result = parse_generic_csv(file)

        assert result.rows[0].asset_class is None
        assert result.rows[0].external_id is None
        assert result.rows[0].fx_rate is None

    def test_raises_for_invalid_type(self) -> None:
        file = _csv(
            """
            date,ticker,type,no_of_shares,price_native
            2024-01-10,VOD,DIVIDEND,50,1.3
            """.replace("            ", "")
        )

        with pytest.raises(ImportParseError, match="BUY or SELL"):
            parse_generic_csv(file)

    def test_raises_for_missing_required_column(self) -> None:
        file = _csv("date,ticker,type,no_of_shares\n2024-01-10,VOD,BUY,50\n")

        with pytest.raises(ImportParseError, match="price_native"):
            parse_generic_csv(file)


def test_presets_registry_contains_both_presets() -> None:
    assert set(PRESETS) == {"generic", "trading212"}
    assert PRESETS["generic"] is parse_generic_csv
    assert PRESETS["trading212"] is parse_trading212_csv
