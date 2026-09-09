import { useEffect, useRef, useState } from "react";
import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";
import "./DiversificationChart.css";

const BAR_TONES = ["accent", "purple", "info", "success", "warning", "danger", "neutral"];

function scoreInfoFor(score) {
  if (score >= 70) return { label: "Well diversified", tone: "success" };
  if (score >= 40) return { label: "Moderately diversified", tone: "warning" };
  return { label: "Concentrated", tone: "danger" };
}

/**
 * A horizontal-bar breakdown chart, used by AccountDetailPage (across every
 * direct + pie-nested holding) and PieDetailPage (scoped to one pie's own
 * holdings) for both Sector and Industry diversification — both real,
 * value-weighted breakdowns built by the shared `buildDiversification`
 * (see ../holdingValuation.js); `caption` should say what `data` actually
 * reflects for that caller. `score` (0-100), when given, renders as a
 * qualitative badge next to the title.
 *
 * Passing `onRowClick` makes rows clickable (used by the Sector chart to
 * drill into the Industry chart) — `activeLabel` then highlights whichever
 * row is currently selected. Neither prop is needed for a read-only chart.
 *
 * Bars grow in from zero on load rather than appearing at full width.
 * `data` is rebuilt (new array identity) on every render of the caller —
 * including ones unrelated to this chart, like an unrelated modal opening —
 * so re-running the reveal on identity change alone would replay it far
 * too often. Instead a content signature (label:pct pairs) is compared
 * against the previous one; the reveal only re-fires when that actually
 * differs, e.g. navigating to a different account/pie, or the Sector
 * chart's onRowClick filtering the Industry chart's rows.
 */
function DiversificationChart({ title, caption, data, score, onRowClick, activeLabel }) {
  const scoreInfo = typeof score === "number" ? scoreInfoFor(score) : null;
  const signature = data.map((entry) => `${entry.label}:${entry.pct}`).join("|");
  const prevSignatureRef = useRef(null);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (prevSignatureRef.current === signature) return undefined;
    prevSignatureRef.current = signature;
    setRevealed(false);
    const frame = requestAnimationFrame(() => setRevealed(true));
    return () => cancelAnimationFrame(frame);
  }, [signature]);

  return (
    <Card className="ec-divchart ec-detail-section">
      <div className="ec-divchart-head">
        <h3 className="ec-divchart-title">{title}</h3>
        {scoreInfo && (
          <Badge tone={scoreInfo.tone}>
            {score}/100 · {scoreInfo.label}
          </Badge>
        )}
      </div>
      {data.length === 0 ? (
        <p className="ec-divchart-empty">Nothing to show for this filter.</p>
      ) : (
        <div className="ec-divchart-bars">
          {data.map((entry, i) => {
            const isActive = entry.label === activeLabel;
            const row = (
              <>
                <span className="ec-divchart-label">{entry.label}</span>
                <div className="ec-divchart-track">
                  <div
                    className={`ec-divchart-fill ec-divchart-fill--${BAR_TONES[i % BAR_TONES.length]}`}
                    style={{
                      width: revealed ? `${entry.pct}%` : "0%",
                      transitionDelay: `${i * 60}ms`,
                    }}
                  />
                </div>
                <span className="ec-divchart-pct">{entry.pct}%</span>
              </>
            );
            return onRowClick ? (
              <button
                type="button"
                key={entry.label}
                className={`ec-divchart-row ec-divchart-row--clickable${isActive ? " is-active" : ""}`}
                aria-pressed={isActive}
                onClick={() => onRowClick(entry.label)}
              >
                {row}
              </button>
            ) : (
              <div className="ec-divchart-row" key={entry.label}>
                {row}
              </div>
            );
          })}
        </div>
      )}
      {caption && <p className="ec-chart-caption">{caption}</p>}
    </Card>
  );
}

export default DiversificationChart;
