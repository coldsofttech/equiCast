import CandlestickSpearIcon from "./CandlestickSpearIcon.jsx";
import "./Logo.css";

/**
 * The equiCast brand mark: gradient badge (Candlestick Spear icon) plus
 * the "equi**Cast**" wordmark. All CSS-driven (no image request), reading
 * `--ec-accent`/`--ec-purple` so it flips with the theme toggle for free —
 * this is the "CSS logo for web" half of the design decision in
 * docs/design/README.md; the static SVG exports (email, favicon, etc.)
 * are a separate, not-yet-produced deliverable.
 *
 * `compact` renders the badge alone — for constrained spaces (a collapsed
 * sidebar, a tight mobile header) where the full wordmark doesn't fit.
 */
function Logo({ compact = false }) {
  return (
    <span className="ec-logo">
      <span className="ec-logo-badge">
        <CandlestickSpearIcon />
      </span>
      {!compact && (
        <span className="ec-logo-wordmark">
          equi<b>Cast</b>
        </span>
      )}
    </span>
  );
}

export default Logo;
