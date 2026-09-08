import SECTORS from "../../config/sectors.json";

/**
 * Static UK/US-only option lists for SearchFilters' Region/Exchange
 * dropdowns — a curated list rather than a dynamic distinct-values lookup
 * from the catalog, since equiCast's ticker list is presently hand-picked
 * from just these two countries (see packages/*\/config/*.yaml). Values
 * are the exact raw codes the search catalog stores (see
 * equicast_core.catalog.build_catalog_rows) and `MarketDataClient.search`
 * matches case-insensitively against `region`/`exchange` — `region` is
 * yfinance's own short country code (e.g. "us"/"gb"), and `exchange` is
 * yfinance's own exchange code (e.g. "NMS"/"PCX"), not a bare
 * "NASDAQ"/"NYSE" string, so the label here is what's shown, not what's
 * sent. Extend both lists (and MarketDataClient.search's docstring, which
 * says these only meaningfully filter stock/etf) if/when a ticker outside
 * the US/UK is added.
 */
export const REGION_OPTIONS = [
  { value: "", label: "All regions" },
  { value: "us", label: "United States" },
  { value: "gb", label: "United Kingdom" },
];

export const EXCHANGE_OPTIONS = [
  { value: "", label: "All exchanges" },
  { value: "NMS", label: "NASDAQ" },
  { value: "NYQ", label: "NYSE" },
  { value: "PCX", label: "NYSE Arca" },
  { value: "ASE", label: "NYSE American" },
  { value: "LSE", label: "London Stock Exchange" },
];

/**
 * Sector/Industry only ever narrow stock rows today — etf/fx rows carry
 * neither field at all (see equicast_core.catalog.build_catalog_rows and
 * MarketDataClient.search's docstring) and are excluded whenever either
 * filter is applied, the same as a stock row missing the field. Values come
 * from config/sectors.json — yfinance's standard 11 equity sectors (each
 * with its own yfinance industry list) plus "Exchange Traded Fund"/"Mutual
 * Fund" (each its own one-entry "sector") for when those asset classes
 * carry a matching `sector` of their own — etf's ingestion pipeline
 * doesn't set one yet, and equiCast has no mutual-fund asset class at all,
 * so neither currently matches any row. Extend sectors.json if a ticker in
 * a new sector/industry is added.
 */
export const SECTOR_OPTIONS = [
  { value: "", label: "All sectors" },
  ...SECTORS.map(({ name }) => ({ value: name, label: name })),
];

const ALL_INDUSTRIES = [...new Set(SECTORS.flatMap((s) => s.industries))].sort();

/**
 * Industry options for SearchFilters' Industry dropdown, narrowed to the
 * given sector's own yfinance industries — every industry across every
 * sector (deduped, alphabetical) when no sector is selected.
 */
export function getIndustryOptions(sector) {
  const industries = sector ? (SECTORS.find((s) => s.name === sector)?.industries ?? []) : ALL_INDUSTRIES;
  return [{ value: "", label: "All industries" }, ...industries.map((i) => ({ value: i, label: i }))];
}
