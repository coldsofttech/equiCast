import "./IconBadge.css";

/**
 * A stored bootstrap-icons name (bare, e.g. "pie-chart-fill"), rendered as
 * a square glyph badge — same size/shape contract as AssetIcon.jsx (`size`
 * in px, sets both dimensions). Generic display counterpart to IconPicker:
 * that component lets a caller *choose* an icon from some list, this one
 * just *shows* whichever one (or none) ended up stored, falling back to
 * `defaultIcon` so callers never need their own `x.icon ?? ...` fallback.
 * Used for both a pie's icon (PieDetailPage/AccountDetailPage, falling back
 * to config/portfolioIcons.js's DEFAULT_PORTFOLIO_ICON) and an account's
 * (AccountDetailPage/AccountsListPage/AccountCard, falling back to
 * config/accountIcons.js's DEFAULT_ACCOUNT_ICON).
 *
 * @param {{ icon?: string|null, defaultIcon: string, size?: number }} props
 */
function IconBadge({ icon, defaultIcon, size = 24, className, ...rest }) {
  return (
    <span
      className={["ec-icon-badge", className].filter(Boolean).join(" ")}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.55) }}
      {...rest}
    >
      <i className={`bi bi-${icon || defaultIcon}`} aria-hidden="true" />
    </span>
  );
}

export default IconBadge;
