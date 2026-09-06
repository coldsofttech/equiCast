import { useEffect, useState } from "react";
import Badge from "../../components/core/Badge.jsx";
import Card from "../../components/core/Card.jsx";
import { useApi } from "../../api/useApi.js";
import { getMetrics } from "../../api/market.js";
import { RATED_METRICS, compareMetric, scoreInfoFor } from "../holdings/HoldingBenchmarkRating.jsx";
import "../holdings/HoldingBenchmarkRating.css";

/**
 * Weights each holding's own `key` metric by its current value (see
 * PieDetailPage's `computeHoldingValuation`), renormalized among whichever
 * holdings actually have that metric published — a holding missing it (too
 * recently listed, or a metric field that isn't published for it) is
 * excluded from that metric's average entirely rather than counted as 0,
 * same "just skip it" reasoning HoldingBenchmarkRating applies per-holding.
 * A zero-share/zero-value holding naturally drops out on its own (its
 * weight is 0), no separate filtering needed. `null` when no holding has
 * this metric at all. Exported so PieCagrSection weights its own cagr_*
 * fields the exact same way.
 */
export function weightedPortfolioMetric(metricsByHolding, valuations, key) {
  let weightedSum = 0;
  let totalWeight = 0;
  metricsByHolding.forEach((metrics, i) => {
    const value = metrics?.[key];
    if (value == null) return;
    const weight = valuations[i].currentValue;
    weightedSum += value * weight;
    totalWeight += weight;
  });
  return totalWeight > 0 ? weightedSum / totalWeight : null;
}

/**
 * PiePriceChart's own version of HoldingBenchmarkRating — same 0-100
 * "beats the benchmark on N of `RATED_METRICS.length`" score and row
 * breakdown (reusing that component's own RATED_METRICS/compareMetric/
 * scoreInfoFor), but the "holding" side is a current-value-weighted average
 * of every one of the pie's own holdings' real `GET .../metrics/` (see
 * weightedPortfolioMetric) rather than one ticker's own figures.
 *
 * This is a simplification, most notably for sharpe_ratio: a true
 * portfolio Sharpe ratio depends on covariances between holdings, not just
 * a weighted average of their individual ratios. Same "reasonable
 * heuristic, not a rigorous metric" tradeoff this page already makes for
 * its own sectorScore (see buildDiversification).
 *
 * @param {{ holdings: import("../../api/accounts.js").Holding[], valuations: { currentValue: number }[], benchmarkKey: string, benchmarkLabel: string }} props
 */
function PieBenchmarkRating({ holdings, valuations, benchmarkKey, benchmarkLabel }) {
  const api = useApi();
  const [metricsByHolding, setMetricsByHolding] = useState(null);
  const [benchmarkMetrics, setBenchmarkMetrics] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    Promise.all([
      Promise.all(holdings.map((h) => getMetrics(api, h.asset_class, h.ticker).catch(() => null))),
      getMetrics(api, "benchmark", benchmarkKey),
    ])
      .then(([perHolding, benchmark]) => {
        if (cancelled) return;
        setMetricsByHolding(perHolding);
        setBenchmarkMetrics(benchmark);
        setStatus("ok");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [api, holdings, benchmarkKey]);

  if (status === "loading") {
    return <p className="ec-chart-caption">Rating this portfolio against {benchmarkLabel}…</p>;
  }
  if (status === "error") {
    return <p className="ec-chart-caption">Couldn&rsquo;t load a rating against {benchmarkLabel}.</p>;
  }

  const rows = RATED_METRICS.map(({ key, label, format }) => {
    const portfolioValue = weightedPortfolioMetric(metricsByHolding, valuations, key);
    const benchmarkValue = benchmarkMetrics?.[key];
    return {
      label,
      holdingDisplay: format(portfolioValue) ?? "—",
      benchmarkDisplay: format(benchmarkValue) ?? "—",
      result: compareMetric(portfolioValue, benchmarkValue),
    };
  });
  const rated = rows.filter((row) => row.result !== null);

  if (rated.length === 0) {
    return (
      <p className="ec-chart-caption">
        Not enough overlapping data to rate this portfolio against {benchmarkLabel} yet.
      </p>
    );
  }

  const wins = rated.filter((row) => row.result === "beats").length;
  const score = Math.round((wins / rated.length) * 100);
  const scoreInfo = scoreInfoFor(score);

  return (
    <Card className="ec-benchmark-rating">
      <div className="ec-benchmark-rating-head">
        <h4 className="ec-benchmark-rating-title">Rating vs {benchmarkLabel}</h4>
        <Badge tone={scoreInfo.tone}>
          {score}/100 · {scoreInfo.label}
        </Badge>
      </div>
      <div className="ec-benchmark-rating-rows">
        {rows.map((row) => (
          <div className="ec-benchmark-rating-row" key={row.label}>
            <span className="ec-benchmark-rating-label">{row.label}</span>
            <span className="ec-benchmark-rating-value">{row.holdingDisplay}</span>
            <span className="ec-benchmark-rating-value">{row.benchmarkDisplay}</span>
            <span
              className={
                row.result === "beats"
                  ? "ec-benchmark-rating-result is-up"
                  : row.result === "trails"
                    ? "ec-benchmark-rating-result is-down"
                    : "ec-benchmark-rating-result"
              }
            >
              {row.result === "beats" ? "▲" : row.result === "trails" ? "▼" : "—"}
            </span>
          </div>
        ))}
      </div>
      <p className="ec-chart-caption">
        Beats the benchmark on {wins} of {rated.length} metric{rated.length === 1 ? "" : "s"} this
        portfolio and {benchmarkLabel} both have data for — each figure is a current-value-weighted
        average across the portfolio's own holdings, not a true covariance-aware portfolio metric.
      </p>
    </Card>
  );
}

export default PieBenchmarkRating;
