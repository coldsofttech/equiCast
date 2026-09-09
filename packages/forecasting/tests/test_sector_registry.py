import pytest
from equicast_forecasting.sector_registry import SECTOR_SCHEMAS, UnroutableSectorError, route_sector

#: (sector, industry, expected_schema_key) - real yfinance sector/industry
#: strings, verified live against JPM/AIG/BLK/PFE/MRNA/PG/XOM/NEE/O/NLY/
#: CBRE/CAT/FCX/T/AMZN/TSLA/META/GOOGL/AAPL/MSFT/NVDA before writing this
#: registry.
ROUTING_CASES = [
    ("Technology", "Semiconductors", "technology"),
    ("Technology", "Software - Infrastructure", "technology"),
    ("Technology", "Consumer Electronics", "technology"),
    ("Financial Services", "Banks - Diversified", "financial_services_banks"),
    ("Financial Services", "Banks - Regional", "financial_services_banks"),
    ("Financial Services", "Mortgage Finance", "financial_services_banks"),
    ("Financial Services", "Insurance - Diversified", "financial_services_insurance"),
    ("Financial Services", "Insurance - Life", "financial_services_insurance"),
    ("Financial Services", "Asset Management", "financial_services_asset_management"),
    ("Financial Services", "Capital Markets", "financial_services_asset_management"),
    ("Financial Services", "Credit Services", "financial_services_asset_management"),
    ("Healthcare", "Drug Manufacturers - General", "healthcare_pharma_devices"),
    ("Healthcare", "Medical Devices", "healthcare_pharma_devices"),
    ("Healthcare", "Diagnostics & Research", "healthcare_pharma_devices"),
    ("Healthcare", "Biotechnology", "healthcare_biotech"),
    ("Consumer Defensive", "Household & Personal Products", "consumer_defensive"),
    ("Consumer Defensive", "Packaged Foods", "consumer_defensive"),
    ("Consumer Cyclical", "Internet Retail", "consumer_cyclical"),
    ("Consumer Cyclical", "Auto Manufacturers", "consumer_cyclical"),
    ("Communication Services", "Internet Content & Information", "communication_services"),
    ("Communication Services", "Telecom Services", "communication_services"),
    ("Utilities", "Utilities - Regulated Electric", "utilities"),
    ("Real Estate", "REIT - Retail", "real_estate_reit_equity"),
    ("Real Estate", "REIT - Residential", "real_estate_reit_equity"),
    ("Real Estate", "REIT - Mortgage", "real_estate_reit_mortgage"),
    ("Real Estate", "Real Estate Services", "real_estate_non_reit"),
    ("Energy", "Oil & Gas Integrated", "energy"),
    ("Energy", "Oil & Gas E&P", "energy"),
    ("Basic Materials", "Copper", "basic_materials"),
    ("Basic Materials", "Chemicals", "basic_materials"),
    ("Industrials", "Farm & Heavy Construction Machinery", "industrials"),
    ("Industrials", "Airlines", "industrials"),
]


@pytest.mark.parametrize(("sector", "industry", "expected_key"), ROUTING_CASES)
def test_route_sector_matches_expected_schema(
    sector: str, industry: str, expected_key: str
) -> None:
    assert route_sector(sector, industry).key == expected_key


def test_route_sector_raises_for_unknown_sector() -> None:
    with pytest.raises(UnroutableSectorError):
        route_sector("Not A Real Sector", "Whatever")


def test_route_sector_raises_for_financial_services_with_unmatched_industry() -> None:
    # Financial Services has no bare fallback entry - an industry matching
    # none of the three sub-schemas must still raise, not silently route
    # to Banks/Insurance/AssetManagement.
    with pytest.raises(UnroutableSectorError):
        route_sector("Financial Services", "Something Else Entirely")


def test_route_sector_raises_for_healthcare_with_unmatched_industry() -> None:
    with pytest.raises(UnroutableSectorError):
        route_sector("Healthcare", "Something Else Entirely")


def test_route_sector_raises_for_real_estate_with_unmatched_industry() -> None:
    with pytest.raises(UnroutableSectorError):
        route_sector("Real Estate", "Something Else Entirely")


def test_route_sector_raises_for_none_sector_or_industry() -> None:
    with pytest.raises(UnroutableSectorError):
        route_sector(None, None)


def test_unroutable_sector_error_carries_sector_and_industry() -> None:
    try:
        route_sector("Not A Real Sector", "Some Industry")
    except UnroutableSectorError as error:
        assert error.sector == "Not A Real Sector"
        assert error.industry == "Some Industry"
    else:
        pytest.fail("expected UnroutableSectorError")


def test_reit_equity_does_not_match_mortgage_industry() -> None:
    assert route_sector("Real Estate", "REIT - Mortgage").key == "real_estate_reit_mortgage"


def test_all_sixteen_branches_are_registered() -> None:
    assert len(SECTOR_SCHEMAS) == 16
    assert len({schema.key for schema in SECTOR_SCHEMAS}) == 16


def test_every_schema_declares_all_three_horizons() -> None:
    for schema in SECTOR_SCHEMAS:
        assert set(schema.parameters.keys()) == {"short", "medium", "long"}
        for horizon_params in schema.parameters.values():
            assert len(horizon_params) > 0


def test_valuation_multiple_is_one_of_the_known_families_or_none() -> None:
    known_families = {"pe", "pe_tangible_book", "price_to_book", "book_value"}
    for schema in SECTOR_SCHEMAS:
        assert schema.valuation_multiple is None or schema.valuation_multiple in known_families
