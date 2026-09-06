import { useEffect, useState } from "react";
import Card from "../../components/core/Card.jsx";
import { useApi } from "../../api/useApi.js";
import { getMetrics } from "../../api/market.js";
import { plTone } from "../sampleFinancials.js";
import { formatPercent } from "../holdings/holdingFinancials.js";
import { weightedPortfolioMetric } from "./PieBenchmarkRating.jsx";
import "../holdings/HoldingTickerPage.css";

/** Same trailing windows/labels as HoldingCagrSection — see that
 * component's own docstring for why they're "-"-prefixed. */
const CAGR_PERIODS = [
  { key: "cagr_10y", label: "-10Y" },
  { key: "cagr_5y", label: "-5Y" },
  { key: "cagr_3y", label: "-3Y" },
  { key: "cagr_2y", label: "-2Y" },
  { key: "cagr_1y", label: "-1Y" },
];

/**
 * PieDetailPage's own version of HoldingCagrSection — same diverging-bar
 * list off real `GET .../metrics/` cagr_* fields (reusing the same
 * `ec-cagr-*` styling), but each period is a current-value-weighted average
 * across every one of the pie's own holdings (see PieBenchmarkRating's
 * weightedPortfolioMetric) rather than one ticker's own figure. A holding
 * missing a given window (too recently listed) is excluded from that
 * window's average entirely, same "just skip it" reasoning
 * HoldingCagrSection applies to a single ticker's own missing windows.
 *
 * Renders nothing while metrics haven't loaded yet, or once loaded if no
 * holding has any cagr_* field at all (e.g. every holding too recently
 * listed to annualize).
 *
 * @param {{ holdings: import("../../api/accounts.js").Holding[], valuations: { currentValue: number }[] }} props
 */
function PieCagrSection({ holdings, valuations }) {
  const api = useApi();
  const [metricsByHolding, setMetricsByHolding] = useState(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all(holdings.map((h) => getMetrics(api, h.asset_class, h.ticker).catch(() => null))).then(
      (results) => {
        if (!cancelled) setMetricsByHolding(results);
      }
    );
    return () => {
      cancelled = true;
    };
  }, [api, holdings]);

  if (!metricsByHolding) return null;

  const rows = CAGR_PERIODS.map(({ key, label }) => ({
    label,
    value: weightedPortfolioMetric(metricsByHolding, valuations, key),
  })).filter((row) => row.value != null);

  if (rows.length === 0) return null;

  const maxAbs = Math.max(...rows.map((row) => Math.abs(row.value)));

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">CAGR</h3>
      </div>

      <div className="ec-cagr-list">
        {rows.map(({ label, value }) => {
          const tone = plTone(value * 100);
          const barPct = maxAbs > 0 ? (Math.abs(value) / maxAbs) * 50 : 0;
          return (
            <div className="ec-cagr-row" key={label}>
              <span className="ec-cagr-period">{label}</span>
              <div className="ec-cagr-bar-track">
                <div className="ec-cagr-bar-zero" />
                <div
                  className={`ec-cagr-bar-segment ${tone}`}
                  style={value >= 0 ? { left: "50%", width: `${barPct}%` } : { right: "50%", width: `${barPct}%` }}
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
      <p className="ec-chart-caption">
        Compound annual growth rate, annualized over each trailing return window — each figure is a
        current-value-weighted average across the portfolio&rsquo;s own holdings.
      </p>
    </Card>
  );
}

export default PieCagrSection;
