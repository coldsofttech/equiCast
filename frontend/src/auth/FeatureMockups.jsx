import "./FeatureMockups.css";

/**
 * Small hand-rolled, illustrative-data visuals for the landing page's
 * feature spotlights — same "no charting library" approach as DemoChart,
 * but with made-up numbers since these accompany features (pies,
 * diversification, since-inception performance) that have no meaningful
 * unauthenticated data source of their own.
 */

const PIE_SEGMENTS = [
  { label: "Core ETFs", pct: 45, color: "var(--ec-accent)" },
  { label: "Growth stocks", pct: 25, color: "var(--ec-purple)" },
  { label: "Dividend payers", pct: 20, color: "var(--ec-success)" },
  { label: "Cash", pct: 10, color: "var(--ec-warning)" },
];

export function PortfolioPiesMockup() {
  let acc = 0;
  const stops = PIE_SEGMENTS.map((s) => {
    const start = acc;
    acc += s.pct;
    return `${s.color} ${start}% ${acc}%`;
  }).join(", ");

  return (
    <div className="ec-mockup ec-mockup-pie" aria-hidden="true">
      <div className="ec-mockup-pie-donut" style={{ background: `conic-gradient(${stops})` }}>
        <div className="ec-mockup-pie-hole" />
      </div>
      <ul className="ec-mockup-pie-legend">
        {PIE_SEGMENTS.map((s) => (
          <li key={s.label}>
            <span className="ec-mockup-dot" style={{ background: s.color }} />
            {s.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

const SECTORS = [
  { label: "Technology", pct: 35, color: "var(--ec-accent)" },
  { label: "Healthcare", pct: 20, color: "var(--ec-purple)" },
  { label: "Financials", pct: 18, color: "var(--ec-info)" },
  { label: "Energy", pct: 15, color: "var(--ec-warning)" },
  { label: "Other", pct: 12, color: "var(--ec-success)" },
];

export function DiversificationMockup() {
  return (
    <div className="ec-mockup ec-mockup-diversification" aria-hidden="true">
      <div className="ec-mockup-bar">
        {SECTORS.map((s) => (
          <span key={s.label} className="ec-mockup-bar-segment" style={{ width: `${s.pct}%`, background: s.color }} />
        ))}
      </div>
      <div className="ec-mockup-bar-legend">
        {SECTORS.map((s) => (
          <span key={s.label} className="ec-mockup-bar-legend-item">
            <span className="ec-mockup-dot" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
      <span className="ec-mockup-benchmark-badge">▲ 3.1% vs. S&amp;P 500</span>
    </div>
  );
}

const INVESTED_PATH = "M2,58 L20,54 L40,50 L60,46 L80,42 L98,38";
const CURRENT_PATH = "M2,58 L20,50 L40,44 L60,32 L80,20 L98,8";
const CURRENT_AREA = `${CURRENT_PATH} L98,60 L2,60 Z`;

export function PerformanceMockup() {
  return (
    <div className="ec-mockup ec-mockup-performance" aria-hidden="true">
      <svg viewBox="0 0 100 60" className="ec-mockup-performance-svg" preserveAspectRatio="none">
        <path d={CURRENT_AREA} className="ec-mockup-performance-area" />
        <path d={INVESTED_PATH} className="ec-mockup-performance-line ec-mockup-performance-line--invested" fill="none" />
        <path d={CURRENT_PATH} className="ec-mockup-performance-line ec-mockup-performance-line--current" fill="none" />
      </svg>
      <div className="ec-mockup-performance-legend">
        <span>
          <span className="ec-mockup-dot ec-mockup-dot--muted" /> Invested
        </span>
        <span>
          <span className="ec-mockup-dot ec-mockup-dot--accent" /> Current value
        </span>
      </div>
    </div>
  );
}
