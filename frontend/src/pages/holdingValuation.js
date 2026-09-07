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
