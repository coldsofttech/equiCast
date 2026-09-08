import { DEFAULT_PORTFOLIO_ICON } from "../../config/portfolioIcons.js";
import "./PortfolioIcon.css";

/**
 * A pie's `icon` (bare bootstrap-icons name), rendered as a square glyph
 * badge — same size/shape contract as AssetIcon.jsx (`size` in px, sets
 * both dimensions) so it drops into the same slots (PieDetailPage's
 * titleIcon, AccountDetailPage's/PieDetailPage's detail-row-heading).
 * Falls back to DEFAULT_PORTFOLIO_ICON for a pie with no icon set (every
 * pie that predates this field), so callers never need their own
 * `pie.icon ?? ...` fallback.
 *
 * @param {{ icon?: string|null, size?: number }} props
 */
function PortfolioIcon({ icon, size = 24, className, ...rest }) {
  return (
    <span
      className={["ec-portfolio-icon", className].filter(Boolean).join(" ")}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.55) }}
      {...rest}
    >
      <i className={`bi bi-${icon || DEFAULT_PORTFOLIO_ICON}`} aria-hidden="true" />
    </span>
  );
}

export default PortfolioIcon;
