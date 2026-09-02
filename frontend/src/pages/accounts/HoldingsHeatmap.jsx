import { useMemo } from "react";
import Card from "../../components/core/Card.jsx";
import { seededRandom } from "../../utils/deterministicRandom.js";
import { squarify } from "../../utils/treemap.js";
import "./HoldingsHeatmap.css";

/**
 * Stand-in for a real 50-holding portfolio, used only when `tickers` is
 * empty so the heatmap has something to illustrate rather than sitting on
 * an empty state — see the `caption` note below.
 */
const SAMPLE_TICKERS = [
  "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JPM", "V",
  "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD", "CVX", "MRK", "ABBV",
  "PEP", "KO", "COST", "AVGO", "ADBE", "CSCO", "TMO", "MCD", "ACN", "CRM",
  "NFLX", "DIS", "ABT", "DHR", "NKE", "LIN", "TXN", "PM", "NEE", "UPS",
  "BMY", "RTX", "HON", "ORCL", "QCOM", "LOW", "AMD", "INTC", "IBM", "GE",
];

/** Layout-only virtual coordinate space — see `.ec-heatmap`'s matching
 * aspect-ratio in HoldingsHeatmap.css, which is what makes squarify's
 * rectangles line up with the container's actual on-screen proportions
 * without needing a ResizeObserver. */
const LAYOUT_W = 1200;
const LAYOUT_H = 480;

/** The change% a tile has to reach for full color saturation — matches a
 * standard market-heatmap legend (see .ec-heatmap-legend) rather than
 * scaling relative to this sample's own min/max move. */
const MAX_ABS_CHANGE_PCT = 30;

function buildWeights(tickers) {
  return tickers.map((ticker) => ({ ticker, raw: 1 + seededRandom(`weight:${ticker}`)() * 4 }));
}

/** Synthetic "today" move per ticker, roughly ±8% — see caption. */
function buildChange(ticker) {
  return (seededRandom(`change:${ticker}`)() - 0.5) * 16;
}

function toneFor(changePct) {
  const isUp = changePct >= 0;
  const intensity = Math.round(15 + Math.min(Math.abs(changePct), MAX_ABS_CHANGE_PCT) * (70 / MAX_ABS_CHANGE_PCT));
  const tone = isUp ? "var(--ec-success)" : "var(--ec-danger)";
  return {
    isUp,
    intensity,
    background: `color-mix(in srgb, ${tone} ${intensity}%, var(--ec-surface))`,
    color: intensity > 55 ? "var(--ec-text-on-accent)" : "var(--ec-text)",
  };
}

/**
 * A weight-and-performance heatmap of every distinct ticker held under this
 * account (pies + direct holdings — see AccountDetailPage's `tickers`
 * prop). Tickers are real; weight % and day change are both synthetic (see
 * caption) since equiCast doesn't compute real portfolio valuation or pull
 * live prices yet. Tile *area* is proportional to weight via a squarified
 * treemap layout (see utils/treemap.js); tile *color* is a red-to-green
 * scale on day change, via `color-mix()` against the success/danger tokens
 * so it stays correct in both themes — modeled on a standard market
 * heatmap (Finviz-style: size = weight, color = change).
 *
 * With no real holdings yet, falls back to SAMPLE_TICKERS (50 well-known
 * symbols) so there's something illustrative to look at instead of an
 * empty state — the caption below makes clear when that's happening.
 */
function HoldingsHeatmap({ tickers }) {
  const isSample = tickers.length === 0;

  const cells = useMemo(() => {
    const unique = isSample ? SAMPLE_TICKERS : [...new Set(tickers)];
    const weighted = buildWeights(unique);
    const total = weighted.reduce((sum, w) => sum + w.raw, 0);
    const weightedCells = weighted
      .map((w) => ({
        ticker: w.ticker,
        pct: (w.raw / total) * 100,
        changePct: buildChange(w.ticker),
        area: (w.raw / total) * (LAYOUT_W * LAYOUT_H),
      }))
      .sort((a, b) => b.pct - a.pct);
    return squarify(weightedCells, 0, 0, LAYOUT_W, LAYOUT_H);
  }, [tickers, isSample]);

  return (
    <Card className="ec-detail-section">
      <h3 className="ec-divchart-title">Holdings heatmap</h3>
      <div className="ec-heatmap">
        {cells.map((cell) => {
          const tone = toneFor(cell.changePct);
          const area = cell.w * cell.h;
          const showDetail = area > 3200;
          const showChange = area > 900;
          return (
            <div
              key={cell.ticker}
              className="ec-heatmap-cell"
              title={`${cell.ticker} — ${cell.pct.toFixed(1)}% of account, ${tone.isUp ? "+" : "-"}${Math.abs(cell.changePct).toFixed(1)}% today (sample)`}
              style={{
                left: `${(cell.x / LAYOUT_W) * 100}%`,
                top: `${(cell.y / LAYOUT_H) * 100}%`,
                width: `${(cell.w / LAYOUT_W) * 100}%`,
                height: `${(cell.h / LAYOUT_H) * 100}%`,
                background: tone.background,
                color: tone.color,
              }}
            >
              <span className="ec-heatmap-ticker">{cell.ticker}</span>
              {showChange && (
                <span className="ec-heatmap-change">
                  {tone.isUp ? "▲" : "▼"} {Math.abs(cell.changePct).toFixed(1)}%
                </span>
              )}
              {showDetail && <span className="ec-heatmap-pct">{cell.pct.toFixed(1)}% of account</span>}
            </div>
          );
        })}
      </div>

      <div className="ec-heatmap-legend">
        {[-30, -20, -10, 0, 10, 20, 30].map((pct) => {
          const tone = toneFor(pct);
          return (
            <span className="ec-heatmap-legend-item" key={pct}>
              <span className="ec-heatmap-legend-swatch" style={{ background: tone.background }} />
              {pct > 0 ? `+${pct}` : pct}%
            </span>
          );
        })}
      </div>

      <p className="ec-chart-caption">
        {isSample
          ? "Sample data — showing 50 illustrative holdings until this account has real ones. "
          : "Illustrative weights and day change — "}
        Tile size is weight in the account, tile color is today&rsquo;s (synthetic) move; real
        pricing/weighting is coming.
      </p>
    </Card>
  );
}

export default HoldingsHeatmap;
