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
 * A horizontal-bar breakdown chart, used by AccountDetailPage for both
 * Sector and Industry diversification. `data`/`score` are fully synthetic
 * (see SECTOR_DATA/INDUSTRY_DATA there) — equiCast has no real sector or
 * industry classification source yet; `caption` should say so. `score`
 * (0-100), when given, renders as a qualitative badge next to the title.
 */
function DiversificationChart({ title, caption, data, score }) {
  const scoreInfo = typeof score === "number" ? scoreInfoFor(score) : null;

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
      <div className="ec-divchart-bars">
        {data.map((entry, i) => (
          <div className="ec-divchart-row" key={entry.label}>
            <span className="ec-divchart-label">{entry.label}</span>
            <div className="ec-divchart-track">
              <div
                className={`ec-divchart-fill ec-divchart-fill--${BAR_TONES[i % BAR_TONES.length]}`}
                style={{ width: `${entry.pct}%` }}
              />
            </div>
            <span className="ec-divchart-pct">{entry.pct}%</span>
          </div>
        ))}
      </div>
      {caption && <p className="ec-chart-caption">{caption}</p>}
    </Card>
  );
}

export default DiversificationChart;
