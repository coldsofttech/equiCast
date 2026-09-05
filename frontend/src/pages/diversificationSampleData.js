/**
 * Fully synthetic sector/industry breakdowns and a diversification score,
 * shared by AccountDetailPage and PieDetailPage's DiversificationChart
 * sections — equiCast has no real sector/industry classification source
 * yet (that needs market-data enrichment beyond this phase), so these are
 * fixed placeholder samples rather than derived from any account/pie's
 * actual holdings. See DiversificationChart's `caption` prop for the
 * on-page disclosure.
 */
export const SECTOR_DATA = [
  { label: "Technology", pct: 34 },
  { label: "Healthcare", pct: 18 },
  { label: "Financials", pct: 14 },
  { label: "Consumer Discretionary", pct: 12 },
  { label: "Industrials", pct: 9 },
  { label: "Energy", pct: 7 },
  { label: "Other", pct: 6 },
];

export const SECTOR_SCORE = 72;

/**
 * `sector` ties each industry back to one SECTOR_DATA label, so clicking a
 * sector row in the Sector diversification chart can filter this list down
 * to just its industries (see AccountDetailPage/PieDetailPage) — again a
 * fully synthetic grouping, not a real GICS mapping.
 */
export const INDUSTRY_DATA = [
  { label: "Software", pct: 22, sector: "Technology" },
  { label: "Semiconductors", pct: 16, sector: "Technology" },
  { label: "Banks", pct: 13, sector: "Financials" },
  { label: "Pharmaceuticals", pct: 12, sector: "Healthcare" },
  { label: "E-commerce", pct: 10, sector: "Consumer Discretionary" },
  { label: "Insurance", pct: 8, sector: "Financials" },
  { label: "Utilities", pct: 7, sector: "Industrials" },
  { label: "Other", pct: 12, sector: "Other" },
];
