import { useEffect, useState } from "react";
import Card from "../../components/core/Card.jsx";
import { plTone } from "../sampleFinancials.js";
import { formatPercent } from "./holdingFinancials.js";

/**
 * `MarketMetrics` field/label pairs this section renders, in display order.
 * Labels are prefixed "-" (trailing, e.g. "-1Y") since these are all
 * backward-looking windows off real price history — once forecasting adds
 * a forward CAGR, that'll need "+"-prefixed labels alongside these, not a
 * bare "1Y" that'd be ambiguous between the two. Not every ticker has every
 * window (e.g. a recently-listed stock has no `cagr_10y` yet) — rows with a
 * `null`/missing value are simply skipped rather than shown as "—", so the
 * bars only ever compare windows that actually exist for this ticker.
 *
 * Once `marketMetrics` is ready, each bar segment grows from the zero-line
 * out to its real width (rather than just appearing at full width) —
 * `revealed` starts false on every fresh `marketMetrics`, then flips true
 * on the next frame so there's an actual 0 -> final width change for
 * `.ec-cagr-bar-segment`'s own `transition: width` (HoldingTickerPage.css)
 * to animate — same pattern PieCagrSection uses. Each row's transition-
 * delay is staggered by index so the bars fill in one after another rather
 * than all at once.
 */
const CAGR_PERIODS = [
  { key: "cagr_10y", label: "-10Y" },
  { key: "cagr_5y", label: "-5Y" },
  { key: "cagr_3y", label: "-3Y" },
  { key: "cagr_2y", label: "-2Y" },
  { key: "cagr_1y", label: "-1Y" },
];

/**
 * Real CAGR (compound annual growth rate) figures off `GET .../metrics/`
 * (the `cagr_1y`/`cagr_2y`/`cagr_3y`/`cagr_5y`/`cagr_10y` fields — see
 * market.js's MarketMetrics), one diverging bar per trailing window: each
 * bar grows from a center zero-line, right/green for positive growth,
 * left/red for negative, scaled against whichever available window has the
 * largest magnitude so the set is comparable at a glance. Renders nothing
 * when `marketMetrics` is null or every `cagr_*` field is unset (e.g. an fx
 * pair, or a ticker with too little price history to annualize yet).
 *
 * @param {{ marketMetrics: import("../../api/market.js").MarketMetrics|null }} props
 */
function HoldingCagrSection({ marketMetrics }) {
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (!marketMetrics) return undefined;
    setRevealed(false);
    const frame = requestAnimationFrame(() => setRevealed(true));
    return () => cancelAnimationFrame(frame);
  }, [marketMetrics]);

  const rows = CAGR_PERIODS.map(({ key, label }) => ({ label, value: marketMetrics?.[key] })).filter(
    (row) => row.value != null
  );

  if (rows.length === 0) return null;

  const maxAbs = Math.max(...rows.map((row) => Math.abs(row.value)));

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">CAGR</h3>
      </div>

      <div className="ec-cagr-list">
        {rows.map(({ label, value }, index) => {
          const tone = plTone(value * 100);
          const barPct = maxAbs > 0 ? (Math.abs(value) / maxAbs) * 50 : 0;
          const revealedWidth = revealed ? `${barPct}%` : "0%";
          return (
            <div className="ec-cagr-row" key={label}>
              <span className="ec-cagr-period">{label}</span>
              <div className="ec-cagr-bar-track">
                <div className="ec-cagr-bar-zero" />
                <div
                  className={`ec-cagr-bar-segment ${tone}`}
                  style={
                    value >= 0
                      ? { left: "50%", width: revealedWidth, transitionDelay: `${index * 60}ms` }
                      : { right: "50%", width: revealedWidth, transitionDelay: `${index * 60}ms` }
                  }
                />
              </div>
              <span className={`ec-cagr-value ${tone}`}>
                {value >= 0 ? "+" : "-"}
                {formatPercent(Math.abs(value), 2)}
              </span>
            </div>
          );
        })}
      </div>
      <p className="ec-chart-caption">Compound annual growth rate, annualized over each trailing return window.</p>
    </Card>
  );
}

export default HoldingCagrSection;
