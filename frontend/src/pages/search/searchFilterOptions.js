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
 * Sector/Industry only ever narrow stock rows — etf/fx rows carry neither
 * field at all (see equicast_core.catalog.build_catalog_rows and
 * MarketDataClient.search's docstring) and are excluded whenever either
 * filter is applied, the same as a stock row missing the field. Values are
 * yfinance's own `sector`/`industry` strings for the currently configured
 * stock tickers (see packages/stock/config/*.yaml) — a curated list, same
 * reasoning as REGION_OPTIONS/EXCHANGE_OPTIONS above; extend it if/when a
 * ticker in a new sector/industry is added.
 */
export const SECTOR_OPTIONS = [
  { value: "", label: "All sectors" },
  { value: "Technology", label: "Technology" },
  { value: "Communication Services", label: "Communication Services" },
  { value: "Consumer Cyclical", label: "Consumer Cyclical" },
];

export const INDUSTRY_OPTIONS = [
  { value: "", label: "All industries" },
  { value: "Consumer Electronics", label: "Consumer Electronics" },
  { value: "Software—Infrastructure", label: "Software—Infrastructure" },
  { value: "Internet Content & Information", label: "Internet Content & Information" },
  { value: "Internet Retail", label: "Internet Retail" },
  { value: "Semiconductors", label: "Semiconductors" },
  { value: "Auto Manufacturers", label: "Auto Manufacturers" },
];
