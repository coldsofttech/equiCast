import pytest
from equicast_forecasting.etf_type_registry import (
    CROSS_CUTTING_PARAMETERS,
    ETF_TYPE_SCHEMAS,
    UnroutableEtfTypeError,
    route_etf_type,
)

#: (category, expected_schema_key) - real yfinance `.info["category"]`
#: strings, verified live against VOO/SPY/IVV/VTI/VUG/VOOG/IWM/IJH/VYM/
#: SCHD/VIG/VXUS/VEA/VWO/EWU/EWJ/EWZ/EWG/EWC/FXI/KWEB/INDA/VT/URTH/ACWI/
#: XLK/XLF/XLV/XLE/XLU/SMH/SOXX/ARKG/ICLN/GDX/JETS/VNQ/TQQQ/SQQQ before
#: writing this registry.
ROUTING_CASES = [
    ("Large Blend", "broad_sp"),
    ("Large Growth", "broad_sp"),
    ("Large Value", "broad_sp"),
    ("Mid-Cap Blend", "broad_sp"),
    ("Mid-Cap Growth", "broad_sp"),
    ("Small Blend", "broad_sp"),
    ("Foreign Large Blend", "ftse_regional"),
    ("Diversified Emerging Mkts", "ftse_regional"),
    ("Focused Region", "ftse_regional"),
    ("Japan Stock", "ftse_regional"),
    ("Greater China Region", "ftse_regional"),
    ("India Equity", "ftse_regional"),
    ("Global Large-Stock Blend", "ftse_regional"),
    ("Technology", "thematic_focused"),
    ("Financial", "thematic_focused"),
    ("Health", "thematic_focused"),
    ("Equity Energy", "thematic_focused"),
    ("Utilities", "thematic_focused"),
    ("Equity Precious Metals", "thematic_focused"),
    ("Industrials", "thematic_focused"),
    ("Real Estate", "thematic_focused"),
    ("Miscellaneous Sector", "thematic_focused"),
    ("Trading--Leveraged Equity", "thematic_focused"),
    ("Trading--Inverse Equity", "thematic_focused"),
]


@pytest.mark.parametrize(("category", "expected_key"), ROUTING_CASES)
def test_route_etf_type_matches_expected_schema(category: str, expected_key: str) -> None:
    assert route_etf_type(category).key == expected_key


def test_route_etf_type_raises_for_unknown_category() -> None:
    with pytest.raises(UnroutableEtfTypeError):
        route_etf_type("Not A Real Category")


def test_route_etf_type_raises_for_none_category() -> None:
    with pytest.raises(UnroutableEtfTypeError):
        route_etf_type(None)


def test_unroutable_etf_type_error_carries_category() -> None:
    try:
        route_etf_type("Not A Real Category")
    except UnroutableEtfTypeError as error:
        assert error.category == "Not A Real Category"
    else:
        pytest.fail("expected UnroutableEtfTypeError")


def test_foreign_large_blend_does_not_fall_through_to_broad_sp() -> None:
    # "Foreign Large Blend" contains "Large Blend" as a literal substring -
    # routing order must check ftse_regional before broad_sp's own "Large
    # Blend" substring, or this would misroute.
    assert route_etf_type("Foreign Large Blend").key == "ftse_regional"


def test_all_three_types_are_registered() -> None:
    assert len(ETF_TYPE_SCHEMAS) == 3
    assert {schema.key for schema in ETF_TYPE_SCHEMAS} == {
        "broad_sp",
        "ftse_regional",
        "thematic_focused",
    }


def test_every_schema_declares_all_three_horizons() -> None:
    for schema in ETF_TYPE_SCHEMAS:
        assert set(schema.parameters.keys()) == {"short", "medium", "long"}
        for horizon_params in schema.parameters.values():
            assert len(horizon_params) > 0


def test_cross_cutting_parameters_are_declared() -> None:
    assert CROSS_CUTTING_PARAMETERS == [
        "nav_premium_discount",
        "expense_ratio",
        "tracking_error",
        "concentration_ratio_top10",
    ]
