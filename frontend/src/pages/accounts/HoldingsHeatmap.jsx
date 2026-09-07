import { useMemo } from "react";
import Card from "../../components/core/Card.jsx";
import { seededRandom } from "../../utils/deterministicRandom.js";
import { squarify } from "../../utils/treemap.js";
import "./HoldingsHeatmap.css";

/**
 * Stand-in for a real 50-holding portfolio, used only when `weights` is
 * empty (no real holdings yet) so the heatmap has something to illustrate
 * rather than sitting on an empty state — see the caption rendered below.
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

/**
 * A tile's fill is purely categorical (by weight rank), not a scale of
 * anything — there's no "good"/"bad" tone once the heatmap only shows
 * weight, so this deliberately reuses DiversificationChart's own
 * accent/purple/info/success/warning/danger/neutral badge-soft pairs
 * (background + a text color already designed to read on it) rather than
 * a red/green intensity gradient.
 */
const TILE_TONES = [
  { background: "var(--ec-accent-soft)", color: "var(--ec-accent-soft-text)" },
  { background: "var(--ec-purple-soft)", color: "var(--ec-purple-soft-text)" },
  { background: "var(--ec-info-soft)", color: "var(--ec-info-soft-text)" },
  { background: "var(--ec-success-soft)", color: "var(--ec-success-soft-text)" },
  { background: "var(--ec-warning-soft)", color: "var(--ec-warning-soft-text)" },
  { background: "var(--ec-danger-soft)", color: "var(--ec-danger-soft-text)" },
  { background: "var(--ec-surface-2)", color: "var(--ec-text-muted)" },
];

function buildSampleWeights(tickers) {
  return tickers.map((ticker) => ({ ticker, raw: 1 + seededRandom(`weight:${ticker}`)() * 4 }));
}

/** Turns a list of `{ raw }` weights into `{ pct, area }` tiles, evenly
 * splitting when every raw weight is 0 (e.g. every holding valued at cost
 * basis of 0) rather than dividing by zero. */
function toWeightedCells(weighted) {
  const total = weighted.reduce((sum, w) => sum + w.raw, 0);
  const evenPct = 100 / weighted.length;
  return weighted
    .map((w) => {
      const pct = total > 0 ? (w.raw / total) * 100 : evenPct;
      return { ticker: w.ticker, pct, area: (pct / 100) * (LAYOUT_W * LAYOUT_H) };
    })
    .sort((a, b) => b.pct - a.pct);
}

/**
 * A weight-only treemap of a portfolio's or account's holdings — tile
 * *area* is proportional to weight via a squarified layout (see
 * utils/treemap.js); tile *color* is purely categorical (see TILE_TONES),
 * not a performance scale, since this only ever shows weight.
 *
 * `weights` (`{ ticker, value }[]`) drives real value-based weight —
 * `value` is each holding's current value (see holdingValuation.js's
 * `computeHoldingValuation`), so tile size reflects real weight in whatever
 * `label` names (e.g. "account" for every direct + pie-nested holding, or
 * "portfolio" for one pie's own holdings). An empty `weights` falls back to
 * SAMPLE_TICKERS with a synthetic, deterministic-per-ticker weight so
 * there's something illustrative to look at instead of an empty state.
 */
function HoldingsHeatmap({ weights = [], label = "portfolio" }) {
  const isEmpty = weights.length === 0;

  const cells = useMemo(() => {
    const weighted = isEmpty
      ? buildSampleWeights(SAMPLE_TICKERS)
      : weights.map((w) => ({ ticker: w.ticker, raw: Math.max(w.value, 0) }));
    return toWeightedCells(weighted);
  }, [weights, isEmpty]);

  const layout = useMemo(
    () => squarify(cells, 0, 0, LAYOUT_W, LAYOUT_H),
    [cells]
  );

  return (
    <Card className="ec-detail-section">
      <h3 className="ec-divchart-title">Holdings heatmap</h3>
      <div className="ec-heatmap">
        {layout.map((cell, i) => {
          const tone = TILE_TONES[i % TILE_TONES.length];
          const area = cell.w * cell.h;
          const showDetail = area > 3200;
          return (
            <div
              key={cell.ticker}
              className="ec-heatmap-cell"
              title={`${cell.ticker} — ${cell.pct.toFixed(1)}% of the ${label}${isEmpty ? " (sample)" : ""}`}
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
              {showDetail && <span className="ec-heatmap-pct">{cell.pct.toFixed(1)}%</span>}
            </div>
          );
        })}
      </div>

      {isEmpty && (
        <p className="ec-chart-caption">
          Sample data — showing 50 illustrative holdings until this {label} has real ones. Tile size
          is weight in the {label}.
        </p>
      )}
    </Card>
  );
}

export default HoldingsHeatmap;
