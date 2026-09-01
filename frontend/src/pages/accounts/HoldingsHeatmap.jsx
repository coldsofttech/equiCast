import { useMemo } from "react";
import Card from "../../components/core/Card.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import { seededRandom } from "../../utils/deterministicRandom.js";
import "./HoldingsHeatmap.css";

function buildWeights(tickers) {
  return tickers.map((ticker) => ({ ticker, raw: 1 + seededRandom(`weight:${ticker}`)() * 4 }));
}

/**
 * A weight heatmap of every distinct ticker held under this account (pies
 * + direct holdings — see AccountDetailPage's `tickers` prop). Tickers are
 * real; weight % is synthetic (see caption) since equiCast doesn't compute
 * real portfolio valuation/weighting yet. Tile color intensity scales with
 * weight via `color-mix()` against the accent token, so it stays correct
 * in both themes without a manual light/dark color scale.
 */
function HoldingsHeatmap({ tickers }) {
  const cells = useMemo(() => {
    const unique = [...new Set(tickers)];
    if (unique.length === 0) return [];
    const weighted = buildWeights(unique);
    const total = weighted.reduce((sum, w) => sum + w.raw, 0);
    return weighted
      .map((w) => ({ ticker: w.ticker, pct: (w.raw / total) * 100 }))
      .sort((a, b) => b.pct - a.pct);
  }, [tickers]);

  const maxPct = cells.length > 0 ? cells[0].pct : 0;

  return (
    <Card className="ec-detail-section">
      <h3 className="ec-divchart-title">Holdings heatmap</h3>
      {cells.length === 0 ? (
        <EmptyState
          title="No holdings yet"
          description="Once this account holds tickers (directly or through a pie), they'll show up here weighted by size."
        />
      ) : (
        <>
          <div className="ec-heatmap">
            {cells.map((cell) => {
              const intensity = Math.round(15 + (cell.pct / maxPct) * 70);
              return (
                <div
                  key={cell.ticker}
                  className="ec-heatmap-cell"
                  style={{
                    background: `color-mix(in oklch, var(--ec-accent) ${intensity}%, var(--ec-surface))`,
                    color: intensity > 50 ? "var(--ec-text-on-accent)" : "var(--ec-text)",
                  }}
                >
                  <span className="ec-heatmap-ticker">{cell.ticker}</span>
                  <span className="ec-heatmap-pct">{cell.pct.toFixed(1)}%</span>
                </div>
              );
            })}
          </div>
          <p className="ec-chart-caption">
            Illustrative weights — real portfolio weighting comes once holdings pricing is wired
            up.
          </p>
        </>
      )}
    </Card>
  );
}

export default HoldingsHeatmap;
