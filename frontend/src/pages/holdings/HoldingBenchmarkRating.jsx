import { useEffect, useState } from "react";
import Badge from "../../components/core/Badge.jsx";
import Card from "../../components/core/Card.jsx";
import { useApi } from "../../api/useApi.js";
import { getMetrics } from "../../api/market.js";
import { formatPercent, formatRatio } from "./holdingFinancials.js";
import "./HoldingBenchmarkRating.css";

/** `MarketMetrics` fields this rating compares, in display order — every
 * one is "higher is better" for both a stock/ETF and a benchmark alike, so
 * a single win/loss rule (see `compareMetric` below) covers all four.
 * Deliberately just these — not `volatility`/`max_drawdown` (lower is
 * better there, and folding in mixed-direction metrics would make a bare
 * win-count score harder to reason about) and not `pe_ratio`/other
 * stock-only fundamentals (a benchmark's MetricsClient.metrics() never
 * has them — see equicast_metrics.MetricsClient.fundamentals's
 * docstring), so this rating works the same for any holding, not just
 * stocks. */
const RATED_METRICS = [
  { key: "cagr_1y", label: "1Y CAGR", format: (value) => formatPercent(value) },
  { key: "cagr_3y", label: "3Y CAGR", format: (value) => formatPercent(value) },
  { key: "cagr_5y", label: "5Y CAGR", format: (value) => formatPercent(value) },
  { key: "sharpe_ratio", label: "Sharpe ratio", format: (value) => formatRatio(value) },
];

/** Same 3-band shape as DiversificationChart's own scoreInfoFor (≥70/≥40/
 * else), so a score badge reads consistently wherever equiCast shows one —
 * just performance-framed labels instead of diversification ones. */
function scoreInfoFor(score) {
  if (score >= 70) return { label: "Outperforming", tone: "success" };
  if (score >= 40) return { label: "Tracking the benchmark", tone: "warning" };
  return { label: "Underperforming", tone: "danger" };
}

/** `null` (excluded from the score entirely) when either side is missing —
 * e.g. a recently-listed holding with no `cagr_5y` yet, see
 * HoldingCagrSection's docstring for the same "just skip it" reasoning.
 * Otherwise "beats" only on a strict `>` — a tie (possible for sharpe_ratio
 * landing on the exact same rounded value) doesn't count as a win, but
 * still counts toward the denominator, same as a real loss would. */
function compareMetric(holdingValue, benchmarkValue) {
  if (holdingValue == null || benchmarkValue == null) return null;
  return holdingValue > benchmarkValue ? "beats" : "trails";
}

/**
 * A single 0-100 rating of `ticker` against the benchmark currently picked
 * in HoldingComparePicker — real data, not the fully-synthetic placeholder
 * DiversificationChart's SECTOR_SCORE is (equiCast has no real sector
 * classification source yet; it does have real risk/performance metrics
 * for every asset class, benchmark included — see equicast_metrics).
 *
 * Score = the percentage of RATED_METRICS the holding beats the benchmark
 * on (e.g. 3 of 4 → 75/100), each read from the same `GET .../metrics/`
 * (and same same-day IndexedDB cache) HoldingCagrSection already uses for
 * the holding's own side — deliberately independent of whatever date range
 * is selected in the price chart above, so switching ranges there doesn't
 * make this rating jump around; it only changes when the underlying
 * ingestion pipeline republishes fresher metrics.
 *
 * Renders a plain caption instead of the score/breakdown while there isn't
 * at least one ratable metric on both sides yet — happens for a very
 * recently-listed holding/benchmark pairing with no overlapping CAGR/Sharpe
 * windows.
 *
 * @param {{ assetClass: string, ticker: string, benchmarkKey: string, benchmarkLabel: string }} props
 */
function HoldingBenchmarkRating({ assetClass, ticker, benchmarkKey, benchmarkLabel }) {
  const api = useApi();
  const [holdingMetrics, setHoldingMetrics] = useState(null);
  const [benchmarkMetrics, setBenchmarkMetrics] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    Promise.all([getMetrics(api, assetClass, ticker), getMetrics(api, "benchmark", benchmarkKey)])
      .then(([holding, benchmark]) => {
        if (cancelled) return;
        setHoldingMetrics(holding);
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
  }, [api, assetClass, ticker, benchmarkKey]);

  if (status === "loading") {
    return <p className="ec-chart-caption">Rating {ticker} against {benchmarkLabel}…</p>;
  }
  if (status === "error") {
    return (
      <p className="ec-chart-caption">Couldn&rsquo;t load a rating against {benchmarkLabel}.</p>
    );
  }

  const rows = RATED_METRICS.map(({ key, label, format }) => {
    const holdingValue = holdingMetrics?.[key];
    const benchmarkValue = benchmarkMetrics?.[key];
    return {
      label,
      holdingDisplay: format(holdingValue) ?? "—",
      benchmarkDisplay: format(benchmarkValue) ?? "—",
      result: compareMetric(holdingValue, benchmarkValue),
    };
  });
  const rated = rows.filter((row) => row.result !== null);

  if (rated.length === 0) {
    return (
      <p className="ec-chart-caption">
        Not enough overlapping data to rate {ticker} against {benchmarkLabel} yet.
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
        Beats the benchmark on {wins} of {rated.length} metric{rated.length === 1 ? "" : "s"}{" "}
        {benchmarkLabel} and {ticker} both have data for.
      </p>
    </Card>
  );
}

export default HoldingBenchmarkRating;
