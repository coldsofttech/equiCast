import pytest
from equicast_forecasting.commodity_registry import (
    COMMODITY_CLASS_SCHEMAS,
    UnroutableCommodityError,
    route_commodity_class,
)

#: (future key, expected commodity-class key) - every future currently
#: configured in packages/future/config/futures.prod.yaml, matching the
#: issue's own table exactly.
ROUTING_CASES = [
    ("GOLD", "precious_metals"),
    ("SILVER", "precious_metals"),
    ("PLATINUM", "precious_metals"),
    ("PALLADIUM", "precious_metals"),
    ("CRUDE_OIL_WTI", "energy"),
    ("BRENT_CRUDE", "energy"),
    ("NATURAL_GAS", "energy"),
    ("HEATING_OIL", "energy"),
    ("COPPER", "industrial_metals"),
    ("ALUMINUM", "industrial_metals"),
    ("WHEAT", "grains"),
    ("CORN", "grains"),
    ("SOYBEANS", "grains"),
    ("COFFEE", "softs"),
    ("COTTON", "softs"),
    ("SUGAR", "softs"),
]


@pytest.mark.parametrize(("key", "expected_class_key"), ROUTING_CASES)
def test_route_commodity_class_matches_expected_schema(key: str, expected_class_key: str) -> None:
    assert route_commodity_class(key).key == expected_class_key


def test_route_commodity_class_is_case_insensitive() -> None:
    assert route_commodity_class("gold").key == "precious_metals"


def test_route_commodity_class_raises_for_unknown_key() -> None:
    with pytest.raises(UnroutableCommodityError):
        route_commodity_class("NOT_A_REAL_FUTURE")


def test_route_commodity_class_raises_for_none_key() -> None:
    with pytest.raises(UnroutableCommodityError):
        route_commodity_class(None)


def test_unroutable_commodity_error_carries_key() -> None:
    try:
        route_commodity_class("NOT_A_REAL_FUTURE")
    except UnroutableCommodityError as error:
        assert error.key == "NOT_A_REAL_FUTURE"
    else:
        pytest.fail("expected UnroutableCommodityError")


def test_every_configured_future_is_registered() -> None:
    all_symbols = {symbol for schema in COMMODITY_CLASS_SCHEMAS for symbol in schema.symbols}
    assert all_symbols == {key for key, _ in ROUTING_CASES}


def test_five_commodity_classes_are_registered() -> None:
    assert len(COMMODITY_CLASS_SCHEMAS) == 5
    assert {schema.key for schema in COMMODITY_CLASS_SCHEMAS} == {
        "precious_metals",
        "energy",
        "industrial_metals",
        "grains",
        "softs",
    }


def test_every_schema_declares_all_three_horizons() -> None:
    for schema in COMMODITY_CLASS_SCHEMAS:
        assert set(schema.parameters.keys()) == {"short", "medium", "long"}
        for horizon_params in schema.parameters.values():
            assert len(horizon_params) > 0


def test_no_field_names_reused_from_stock_or_etf_schemas() -> None:
    # Per the issue: "Schema needs to be its own branch, not a reuse of
    # the stock/ETF schema with nulled-out fields."
    stock_etf_field_names = {"starting_pe_vs_history", "valuation_multiple", "trailing_pe"}
    for schema in COMMODITY_CLASS_SCHEMAS:
        for horizon_params in schema.parameters.values():
            assert not stock_etf_field_names.intersection(horizon_params)
