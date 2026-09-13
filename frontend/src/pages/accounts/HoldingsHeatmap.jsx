import { useLayoutEffect, useMemo, useRef, useState } from "react";
import Card from "../../components/core/Card.jsx";
import AssetIcon from "../../components/core/AssetIcon.jsx";
import { squarify } from "../../utils/treemap.js";
import "./HoldingsHeatmap.css";

/** Layout-only virtual coordinate space — see `.ec-heatmap`'s matching
 * aspect-ratio in HoldingsHeatmap.css, which is what keeps squarify's
 * rectangles proportional to the container regardless of its real
 * on-screen size. A cell's real pixel size is `cell.w`/`cell.h` scaled by
 * `containerWidth / LAYOUT_W` (the container's height always follows via
 * the locked aspect-ratio, so one scale factor covers both axes) — see
 * `scale` below, tracked live via ResizeObserver (same pattern as
 * PiePriceChart/HoldingPriceChart) since deciding what a tile can fit
 * needs its *real* size, not just its share of the 1200×480 space. */
const LAYOUT_W = 1200;
const LAYOUT_H = 480;
const DEFAULT_WIDTH = 960;

/**
 * Tile-content tiers, gated on a tile's real rendered size (both width and
 * height must clear the floor — a wide-but-short sliver, e.g. a <1%
 * holding stacked under a much larger one in the same column, can have
 * "enough" area while still being too short for its text to fit).
 * Floors are derived from the CSS actually rendering each line:
 *   ticker line  — --ec-fs-14 (14px) × 1.2 line-height ≈ 16.8px
 *   pct line     — --ec-fs-12 (12px) × 1.2 line-height ≈ 14.4px
 *   icon         — AssetIcon size below (20px)
 *   inter-line gap — --ec-s-2 (2px) each
 *   cell padding — --ec-s-4 (4px) top+bottom = 8px
 *   cell border  — 2px top+bottom = 4px
 * MIN_HEIGHT_FOR_PCT  = 8 + 4 + 16.8 + 2 + 14.4              ≈ 45px, rounded up
 * MIN_HEIGHT_FOR_ICON = 8 + 4 + 20 + 2 + 16.8 + 2 + 14.4     ≈ 67px, rounded up
 * MIN_WIDTH covers the widest common ticker (~6 chars) at that bold mono size.
 */
const MIN_HEIGHT_FOR_PCT = 48;
const MIN_HEIGHT_FOR_ICON = 72;
const MIN_WIDTH_FOR_DETAIL = 56;

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

/** Turns a list of `{ raw }` weights into `{ pct, area }` tiles, evenly
 * splitting when every raw weight is 0 (e.g. every holding valued at cost
 * basis of 0) rather than dividing by zero. Zero-weight holdings are
 * dropped once the total is positive — squarify's worst-ratio scoring
 * divides by a row's smallest area, so a genuine 0-area item produces a
 * NaN-sized rectangle that (with no CSS fallback size) renders as a
 * stray tile sized to fit its text instead of disappearing. */
function toWeightedCells(weighted) {
  const total = weighted.reduce((sum, w) => sum + w.raw, 0);
  if (total <= 0) {
    const evenPct = 100 / weighted.length;
    return weighted
      .map((w) => ({
        ticker: w.ticker,
        website: w.website,
        pct: evenPct,
        area: (evenPct / 100) * (LAYOUT_W * LAYOUT_H),
      }))
      .sort((a, b) => b.pct - a.pct);
  }
  return weighted
    .filter((w) => w.raw > 0)
    .map((w) => {
      const pct = (w.raw / total) * 100;
      return { ticker: w.ticker, website: w.website, pct, area: (pct / 100) * (LAYOUT_W * LAYOUT_H) };
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
 * "portfolio" for one pie's own holdings). An empty `weights` (no holdings
 * yet) renders an empty state instead of synthetic sample tickers, matching
 * DiversificationChart's "nothing to show" treatment.
 */
function HoldingsHeatmap({ weights = [], label = "portfolio" }) {
  const isEmpty = weights.length === 0;
  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(DEFAULT_WIDTH);

  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const boxWidth = entries[0]?.contentRect.width;
      if (boxWidth) setContainerWidth(boxWidth);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const cells = useMemo(() => {
    if (isEmpty) return [];
    return toWeightedCells(
      weights.map((w) => ({ ticker: w.ticker, website: w.website, raw: Math.max(w.value, 0) }))
    );
  }, [weights, isEmpty]);

  const layout = useMemo(() => squarify(cells, 0, 0, LAYOUT_W, LAYOUT_H), [cells]);
  const scale = containerWidth / LAYOUT_W;

  return (
    <Card className="ec-detail-section">
      <h3 className="ec-divchart-title">Holdings heatmap</h3>

      {isEmpty ? (
        <p className="ec-heatmap-empty">Nothing to show — this {label} has no holdings yet.</p>
      ) : (
        <div className="ec-heatmap" ref={containerRef}>
          {layout.map((cell, i) => {
            const tone = TILE_TONES[i % TILE_TONES.length];
            const realW = cell.w * scale;
            const realH = cell.h * scale;
            const wideEnough = realW >= MIN_WIDTH_FOR_DETAIL;
            const showPct = wideEnough && realH >= MIN_HEIGHT_FOR_PCT;
            const showIcon = wideEnough && realH >= MIN_HEIGHT_FOR_ICON;
            return (
              <div
                key={cell.ticker}
                className="ec-heatmap-cell"
                title={`${cell.ticker} — ${cell.pct.toFixed(1)}% of the ${label}`}
                style={{
                  left: `${(cell.x / LAYOUT_W) * 100}%`,
                  top: `${(cell.y / LAYOUT_H) * 100}%`,
                  width: `${(cell.w / LAYOUT_W) * 100}%`,
                  height: `${(cell.h / LAYOUT_H) * 100}%`,
                  background: tone.background,
                  color: tone.color,
                }}
              >
                {showIcon && <AssetIcon website={cell.website} size={20} />}
                <span className="ec-heatmap-ticker">{cell.ticker}</span>
                {showPct && <span className="ec-heatmap-pct">{cell.pct.toFixed(1)}%</span>}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

export default HoldingsHeatmap;
