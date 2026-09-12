import "./NotFoundIcon.css";

/**
 * 404's icon: the same real price-line every chart in equiCast draws
 * (see HoldingPriceChart's own stroke-dasharray reveal), but this one
 * just stops — trailing into a faint dashed line with a searching dot at
 * the end, rather than a market-index-astronaut cliché. Draws itself in
 * once on mount via SVG's `pathLength="1"` (a plain 0→1 CSS animation
 * works regardless of the path's real pixel length, no JS measurement
 * needed, unlike the real chart's own getTotalLength() trick).
 */
function NotFoundIcon() {
  return (
    <svg viewBox="0 0 160 110" fill="none" xmlns="http://www.w3.org/2000/svg">
      <polyline
        points="8,82 32,54 52,68 74,32 94,50 112,40"
        className="ec-erricon-404-line"
        stroke="var(--ec-accent)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength="1"
      />
      <polyline
        points="112,40 128,58 148,50"
        stroke="var(--ec-border-strong)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray="1 6"
      />
      <circle cx="148" cy="50" r="4" className="ec-erricon-404-dot" fill="var(--ec-text-subtle)" />
    </svg>
  );
}

export default NotFoundIcon;
