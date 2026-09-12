import { useEffect, useState } from "react";
import Card from "../../components/core/Card.jsx";
import { formatPercent } from "./holdingFinancials.js";

/**
 * Buy/sell volume-pressure gauge off `GET .../metrics/` (the
 * `buyers_pct`/`sellers_pct` fields — see market.js's MarketMetrics), stock/
 * etf only (see equicast_metrics.MetricsClient.buy_sell_pressure — absent
 * for benchmark/fx). A single stacked bar split at `buyers_pct`, red/left
 * for selling pressure and green/right for buying pressure, with each
 * side's percentage labeled above it — same is-up/is-down (green/red)
 * convention HoldingCagrSection's bars use.
 *
 * Each segment also grows in from 0% width on load rather than appearing
 * at its final size — `revealed` starts false on every fresh
 * `marketMetrics`, then flips true on the next frame so there's an actual
 * 0 -> final-width change for `.ec-buysell-bar-segment`'s `transition:
 * width` (HoldingTickerPage.css) to animate, same pattern
 * HoldingCagrSection/PieCagrSection use for their own bars (GitHub issue
 * #174).
 *
 * This is a technical proxy for order-flow sentiment derived from price and
 * volume action over the trailing year (Chaikin Money Flow's own
 * money-flow-multiplier — see the caption below), not literal buy/sell
 * order counts; yfinance has no real order-book data. Renders nothing when
 * `marketMetrics` is null or `buyers_pct`/`sellers_pct` are unset (an fx/
 * benchmark holding, or a stock/etf with no recorded volume in the window).
 *
 * @param {{ marketMetrics: import("../../api/market.js").MarketMetrics|null }} props
 */
function HoldingBuySellGauge({ marketMetrics }) {
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (!marketMetrics) return undefined;
    setRevealed(false);
    const frame = requestAnimationFrame(() => setRevealed(true));
    return () => cancelAnimationFrame(frame);
  }, [marketMetrics]);

  const buyersPct = marketMetrics?.buyers_pct;
  const sellersPct = marketMetrics?.sellers_pct;
  if (buyersPct == null || sellersPct == null) return null;

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">Buy/Sell Rating</h3>
      </div>

      <div className="ec-buysell-head">
        <span className="ec-buysell-value is-down">{formatPercent(sellersPct, 0)}</span>
        <span className="ec-buysell-label">Sellers / Buyers</span>
        <span className="ec-buysell-value is-up">{formatPercent(buyersPct, 0)}</span>
      </div>
      <div className="ec-buysell-bar-track">
        <div
          className="ec-buysell-bar-segment is-down"
          style={{ width: revealed ? `${sellersPct * 100}%` : "0%" }}
        />
        <div
          className="ec-buysell-bar-segment is-up"
          style={{ width: revealed ? `${buyersPct * 100}%` : "0%" }}
        />
      </div>

      <p className="ec-chart-caption">
        Buy/sell volume pressure over the trailing year, derived from price and volume action — a
        technical proxy for order-flow sentiment, not literal buy/sell order counts.
      </p>
    </Card>
  );
}

export default HoldingBuySellGauge;
