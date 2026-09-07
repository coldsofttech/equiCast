/**
 * Derives one holding's current value/profit-loss from its already
 * rolled-up fields (`no_of_shares`/`invested`) and its enriched
 * `current_price` (see backend `equicast_core.client.MarketDataClient.
 * enrich_holdings`, applied to both /accounts and /pies holdings — see
 * api/accounts.js's `Holding` typedef). `current_price` is `null` when the
 * ticker isn't published or no FX rate exists for it — in that case this
 * falls back to valuing the position at its own cost basis (flat P&L)
 * rather than showing a hole in the total, same "degrade gracefully"
 * reasoning as the fields it reads. Shared by AccountDetailPage (account-
 * direct and pie-nested holdings alike) and PieDetailPage, whose holdings
 * carry the identical shape.
 */
export function computeHoldingValuation(holding) {
  const invested = Number(holding.invested) || 0;
  const shares = Number(holding.no_of_shares) || 0;
  const livePrice = holding.current_price;
  const currentValue = livePrice != null ? shares * livePrice : invested;
  const plValue = currentValue - invested;
  const plPct = invested !== 0 ? (plValue / invested) * 100 : 0;
  return { invested, currentValue, plValue, plPct, hasLivePrice: livePrice != null };
}

/**
 * Sums `computeHoldingValuation` results (`valuations`, one per entry in
 * `holdings`, same order) into a single invested/currentValue/dividends
 * total across every holding, plus the resulting overall plValue/plPct —
 * used for a page-level Value/Profit-loss/Dividends-so-far stat row.
 */
export function summarizeHoldingValuations(holdings, valuations) {
  const totals = holdings.reduce(
    (sum, holding, index) => ({
      invested: sum.invested + valuations[index].invested,
      currentValue: sum.currentValue + valuations[index].currentValue,
      dividends: sum.dividends + (Number(holding.dividends) || 0),
    }),
    { invested: 0, currentValue: 0, dividends: 0 }
  );
  const plValue = totals.currentValue - totals.invested;
  const plPct = totals.invested !== 0 ? (plValue / totals.invested) * 100 : 0;
  return { ...totals, plValue, plPct };
}

/**
 * Groups `holdings` by sector/industry, weighted by each holding's current
 * value (`valuations`, one per entry in `holdings`, same order — see
 * `computeHoldingValuation`) rather than a plain holding count or
 * `allocation_pct` — a small fx position and a large stock position in the
 * same sector should count as two %-of-value rows, not one-holding-each. A
 * holding with no sector/industry (every etf/fx, or an unpublished ticker —
 * see backend `MarketDataClient.enrich_holdings`) falls into "Other".
 * `sectorScore` is a simple concentration heuristic (100 minus the largest
 * sector's share of value), not a rigorous diversification metric. Shared
 * by AccountDetailPage (across every direct + pie-nested holding) and
 * PieDetailPage (scoped to one pie's holdings).
 */
export function buildDiversification(holdings, valuations) {
  const totalValue = valuations.reduce((sum, v) => sum + v.currentValue, 0);

  const sectorTotals = new Map();
  const industryTotals = new Map();
  holdings.forEach((holding, index) => {
    const value = valuations[index].currentValue;
    sectorTotals.set(holding.sector ?? "Other", (sectorTotals.get(holding.sector ?? "Other") ?? 0) + value);
    const industryKey = holding.industry ?? "Other";
    const existing = industryTotals.get(industryKey);
    if (existing) {
      existing.value += value;
    } else {
      industryTotals.set(industryKey, { value, sector: holding.sector ?? "Other" });
    }
  });

  // Rounded to 1 decimal — DiversificationChart renders `pct` verbatim
  // (`{entry.pct}%`), and an unrounded float would show a long, ugly
  // fractional percentage next to each bar.
  const toPct = (value) => (totalValue > 0 ? Math.round((value / totalValue) * 1000) / 10 : 0);
  const sectorData = [...sectorTotals.entries()]
    .map(([label, value]) => ({ label, pct: toPct(value) }))
    .sort((a, b) => b.pct - a.pct);
  const industryData = [...industryTotals.entries()]
    .map(([label, { value, sector }]) => ({ label, sector, pct: toPct(value) }))
    .sort((a, b) => b.pct - a.pct);
  const sectorScore = sectorData.length > 0 ? Math.round(100 - sectorData[0].pct) : null;

  return { sectorData, industryData, sectorScore };
}

// Only `stock` and `etf` map to a named bucket today — `asset_class` has no
// "mutual fund" or "cash" value yet (see backend holdings/views.py's
// ASSET_CLASSES: fx/stock/etf), so `fx` and anything unmapped falls into
// "Other" rather than guessing at a Cash/Mutual Funds split.
const ASSET_CLASS_LABELS = { stock: "Equities", etf: "ETFs" };

/**
 * Groups `holdings` by asset class, weighted by current value the same way
 * `buildDiversification` groups by sector/industry. Shared by
 * AccountDetailPage and PieDetailPage for their "Asset allocation" chart.
 */
export function buildAssetAllocation(holdings, valuations) {
  const totalValue = valuations.reduce((sum, v) => sum + v.currentValue, 0);

  const totals = new Map();
  holdings.forEach((holding, index) => {
    const label = ASSET_CLASS_LABELS[holding.asset_class] ?? "Other";
    totals.set(label, (totals.get(label) ?? 0) + valuations[index].currentValue);
  });

  const toPct = (value) => (totalValue > 0 ? Math.round((value / totalValue) * 1000) / 10 : 0);
  return [...totals.entries()]
    .map(([label, value]) => ({ label, pct: toPct(value) }))
    .sort((a, b) => b.pct - a.pct);
}

// Standard equity market-cap tiers (the Morningstar/Investopedia
// convention), checked largest-first. `market_cap` is a stock's real
// market cap or an etf's total assets as the closest "size" stand-in (see
// enrich_holdings) — fx holdings and any ticker with no published
// market_cap have no size concept at all, so `buildMarketCapAllocation`
// leaves them out entirely rather than folding them into an "Other"
// bucket the way asset/sector allocation do (explicit product decision).
const MARKET_CAP_TIERS = [
  { label: "Mega Cap", min: 200_000_000_000 },
  { label: "Large Cap", min: 10_000_000_000 },
  { label: "Mid Cap", min: 2_000_000_000 },
  { label: "Small Cap", min: 0 },
];

/**
 * Groups `holdings` by market-cap tier (see MARKET_CAP_TIERS), weighted by
 * current value. Holdings with no `market_cap` are excluded from both the
 * numerator and denominator, so the shown percentages reflect only the
 * holdings a tier could actually be resolved for. Rows come back in fixed
 * Mega->Small order (dropping any tier with no holdings in it) rather than
 * sorted by size, since that progression is the point of the chart. Shared
 * by AccountDetailPage and PieDetailPage for their "Market cap allocation"
 * chart.
 */
export function buildMarketCapAllocation(holdings, valuations) {
  const totals = new Map();
  let totalValue = 0;
  holdings.forEach((holding, index) => {
    const marketCap = holding.market_cap;
    if (marketCap == null) return;
    const value = valuations[index].currentValue;
    totalValue += value;
    const label = MARKET_CAP_TIERS.find((tier) => marketCap >= tier.min).label;
    totals.set(label, (totals.get(label) ?? 0) + value);
  });

  const toPct = (value) => (totalValue > 0 ? Math.round((value / totalValue) * 1000) / 10 : 0);
  return MARKET_CAP_TIERS.map((tier) => tier.label)
    .filter((label) => totals.has(label))
    .map((label) => ({ label, pct: toPct(totals.get(label)) }));
}
