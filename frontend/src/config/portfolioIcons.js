/**
 * Curated bootstrap-icons (https://icons.getbootstrap.com) names offered by
 * IconPicker for a pie's `icon` field (see backend/pies/views.py's
 * OPTIONAL_CREATE_FIELDS/UPDATABLE_FIELDS) — a hand-picked subset rather
 * than the full ~2000-icon set, since bootstrap-icons has no bundled
 * search-by-name index and a wall of every icon would swamp the picker.
 * Extend this list as new use cases come up; IconPicker itself takes
 * whatever `icons` array it's given, so it doesn't need to change.
 *
 * Each value is the bare icon name (e.g. "pie-chart-fill"), not the full
 * "bi bi-pie-chart-fill" class — callers prefix it themselves (see
 * PortfolioIcon.jsx), matching what's stored on the pie.
 */
export const PORTFOLIO_ICON_OPTIONS = [
  "pie-chart-fill",
  "wallet2",
  "piggy-bank-fill",
  "graph-up-arrow",
  "graph-up",
  "bar-chart-fill",
  "cash-coin",
  "cash-stack",
  "coin",
  "currency-exchange",
  "bank",
  "bank2",
  "briefcase-fill",
  "building",
  "gem",
  "globe-americas",
  "house-fill",
  "rocket-takeoff-fill",
  "shield-fill-check",
  "star-fill",
  "sun-fill",
  "tree-fill",
  "trophy-fill",
  "umbrella-fill",
];

/** Rendered by PortfolioIcon (and used as PieForm's implicit choice) for
 * any pie whose `icon` is unset — every pie's icon column predates this
 * feature, so most will hit this fallback until edited. */
export const DEFAULT_PORTFOLIO_ICON = "pie-chart-fill";
