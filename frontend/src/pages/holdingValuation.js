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

/** A `last_updated` value is a full ISO 8601 datetime (see equicast_core's
 * writers) — the Synced badge only needs the date. Shared by
 * HoldingTickerPage (a single ticker's own marketProfile.last_updated) and
 * AccountDetailPage/PieDetailPage (see `minLastUpdated` below). */
export function formatSyncedDate(isoDatetime) {
  const date = new Date(isoDatetime);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/**
 * The oldest `last_updated` among `holdings` (see api/accounts.js's
 * `Holding` typedef) — an account/pie's Synced badge should reflect its
 * stalest holding rather than its freshest, so a user isn't shown a recent
 * date while one ticker's catalog data is actually out of date. Holdings
 * with no `last_updated` (unpublished ticker) are skipped; `null` if none
 * of `holdings` have one (including an empty list).
 */
export function minLastUpdated(holdings) {
  const timestamps = holdings
    .map((h) => h.last_updated)
    .filter(Boolean)
    .map((iso) => ({ iso, time: new Date(iso).getTime() }))
    .filter((entry) => !Number.isNaN(entry.time));
  if (timestamps.length === 0) return null;
  return timestamps.reduce((oldest, entry) => (entry.time < oldest.time ? entry : oldest)).iso;
}
