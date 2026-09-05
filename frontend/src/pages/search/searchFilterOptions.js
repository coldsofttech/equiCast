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
