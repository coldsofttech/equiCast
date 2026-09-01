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

export const INDUSTRY_DATA = [
  { label: "Software", pct: 22 },
  { label: "Semiconductors", pct: 16 },
  { label: "Banks", pct: 13 },
  { label: "Pharmaceuticals", pct: 12 },
  { label: "E-commerce", pct: 10 },
  { label: "Insurance", pct: 8 },
  { label: "Utilities", pct: 7 },
  { label: "Other", pct: 12 },
];
