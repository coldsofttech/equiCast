import { useEffect, useState } from "react";
import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";
import Button from "../../components/core/Button.jsx";
import "./DiversificationChart.css";

const BAR_TONES = ["accent", "purple", "info", "success", "warning", "danger", "neutral"];

function scoreInfoFor(score) {
  if (score >= 70) return { label: "Well diversified", tone: "success" };
  if (score >= 40) return { label: "Moderately diversified", tone: "warning" };
  return { label: "Concentrated", tone: "danger" };
}

/**
 * Sector/Industry diversification (GitHub issue #192) — a single full-width
 * card, sized like the two DiversificationChart cards it replaces combined,
 * that shows only the Sector breakdown by default and swaps in the clicked
 * sector's own Industry breakdown (with a "Back to sectors" way out) rather
 * than always rendering the Sector chart *and* every industry across every
 * sector side by side — the full industry taxonomy (see
 * config/sectors.json) easily produces dozens of rows for a diversified
 * account/pie, which skewed the page. `sectorData`/`industryData`/
 * `sectorScore` are the same real, value-weighted breakdowns
 * `buildDiversification` (../holdingValuation.js) already produces; this
 * owns the sector/industry drill-down state itself (no longer lifted into
 * the caller) since nothing outside this chart depends on it. Reuses
 * DiversificationChart.css's row/bar styling and reveal-on-load animation.
 */
// `industryData` entries carry `pct` of the *whole* portfolio, so a
// straight filter by sector would sum to that sector's own overall share
// (e.g. all of Technology's industries summing to 40.6%) instead of 100% —
// re-derives each row's `pct` against the filtered subset's own total value
// instead, the way a drill-down is expected to read.
function rebaseToSector(entries) {
  const total = entries.reduce((sum, entry) => sum + entry.value, 0);
  if (total <= 0) return entries;
  return entries.map((entry) => ({
    ...entry,
    pct: Math.round((entry.value / total) * 1000) / 10,
  }));
}

function SectorIndustryChart({ sectorData, industryData, sectorScore }) {
  const [selectedSector, setSelectedSector] = useState(null);
  const isIndustryView = selectedSector !== null;
  const data = isIndustryView
    ? rebaseToSector(industryData.filter((entry) => entry.sector === selectedSector))
    : sectorData;
  const scoreInfo = !isIndustryView && typeof sectorScore === "number" ? scoreInfoFor(sectorScore) : null;
  const signature = data.map((entry) => `${entry.label}:${entry.pct}`).join("|");
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    setRevealed(false);
    const frame = requestAnimationFrame(() => setRevealed(true));
    return () => cancelAnimationFrame(frame);
  }, [signature]);

  if (!isIndustryView && data.length === 0) return null;

  return (
    <Card className="ec-divchart ec-divchart-full ec-detail-section">
      <div className="ec-divchart-head">
        <h3 className="ec-divchart-title">
          {isIndustryView ? `Industry diversification — ${selectedSector}` : "Sector diversification"}
        </h3>
        {scoreInfo && (
          <Badge tone={scoreInfo.tone}>
            {sectorScore}/100 · {scoreInfo.label}
          </Badge>
        )}
        {isIndustryView && (
          <Button
            variant="ghost"
            size="sm"
            className="ec-divchart-back"
            onClick={() => setSelectedSector(null)}
          >
            <i className="bi bi-arrow-left" aria-hidden="true" />
            Back to sectors
          </Button>
        )}
      </div>

      {data.length === 0 ? (
        <p className="ec-divchart-empty">Nothing to show for this filter.</p>
      ) : (
        <div className="ec-divchart-bars">
          {data.map((entry, i) => {
            const row = (
              <>
                <span className="ec-divchart-label" title={entry.label}>
                  {entry.label}
                </span>
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
            return isIndustryView ? (
              <div className="ec-divchart-row" key={entry.label}>
                {row}
              </div>
            ) : (
              <button
                type="button"
                key={entry.label}
                className="ec-divchart-row ec-divchart-row--clickable"
                onClick={() => setSelectedSector(entry.label)}
              >
                {row}
              </button>
            );
          })}
        </div>
      )}

      {!isIndustryView && (
        <p className="ec-chart-caption">Click a sector to see its industry breakdown.</p>
      )}
    </Card>
  );
}

export default SectorIndustryChart;
