import { seededRandom } from "../utils/deterministicRandom.js";

/**
 * Synthetic current-value/P&L generators, shared by every page that shows
 * a portfolio/holding "sample" row or summary stat (AccountDetailPage,
 * PieDetailPage, HoldingTickerPage) — equiCast doesn't compute real
 * portfolio valuation or pull live prices yet, so these are illustrative
 * only, deterministic per id via the same seeded-random approach used
 * elsewhere (HoldingsHeatmap, PriceChart).
 */

export function formatCurrency(value, currency) {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

/** A handful of well-known tickers' display names, for a "Name (TICKER)"
 * heading — equiCast has no real company-name lookup yet, so an
 * unrecognized ticker just falls back to showing the ticker alone. */
export const TICKER_NAMES = {
  AAPL: "Apple Inc.",
  MSFT: "Microsoft Corp.",
  GOOGL: "Alphabet Inc.",
  AMZN: "Amazon.com Inc.",
  NVDA: "NVIDIA Corp.",
  META: "Meta Platforms Inc.",
  TSLA: "Tesla Inc.",
  JPM: "JPMorgan Chase & Co.",
  V: "Visa Inc.",
  JNJ: "Johnson & Johnson",
};

/** Synthetic current value / P&L for a pie, deterministic per pie id. */
export function buildPieSample(pieId) {
  const rand = seededRandom(`pie-value:${pieId}`);
  const currentValue = 500 + rand() * 49500;
  const plPct = (rand() - 0.45) * 40;
  const plValue = (currentValue * plPct) / 100;
  return { currentValue, plValue, plPct };
}

/** Synthetic shares held / current value / P&L for one holding *record*,
 * deterministic per holding id — a ticker held in two places (e.g.
 * directly in an account and again inside a pie) is two separate holding
 * ids, so each gets its own independent sample rather than sharing one. */
export function buildHoldingSample(holdingId) {
  const rand = seededRandom(`holding-value:${holdingId}`);
  const shares = Math.max(1, Math.round(1 + rand() * 199));
  const currentValue = 100 + rand() * 19900;
  const plPct = (rand() - 0.45) * 40;
  const plValue = (currentValue * plPct) / 100;
  return { shares, currentValue, plValue, plPct };
}

/** "is-up" / "is-flat" / "is-down" — the shared threshold for coloring a
 * P&L figure (see .ec-detail-row-pl), used wherever a sample P&L renders. */
export function plTone(plPct) {
  if (plPct > 0.05) return "is-up";
  if (plPct < -0.05) return "is-down";
  return "is-flat";
}

/**
 * Rolls up a list of samples (from `buildPieSample`/`buildHoldingSample`)
 * into one total for a page-level summary row (AccountDetailPage's/
 * PieDetailPage's Total Invested / Profit-Loss / Profit-Loss % StatTiles).
 * `invested` (cost basis) is derived as currentValue - plValue rather than
 * sampled separately, so the three totals always agree with each other.
 */
export function aggregateSamples(samples) {
  const currentValue = samples.reduce((sum, s) => sum + s.currentValue, 0);
  const plValue = samples.reduce((sum, s) => sum + s.plValue, 0);
  const invested = currentValue - plValue;
  const plPct = invested !== 0 ? (plValue / invested) * 100 : 0;
  return { currentValue, invested, plValue, plPct };
}
