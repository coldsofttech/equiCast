/**
 * Curated bootstrap-icons (https://icons.getbootstrap.com) names offered by
 * IconPicker for an account's `icon` field (see backend/accounts/views.py's
 * OPTIONAL_CREATE_FIELDS/UPDATABLE_FIELDS) — deliberately a separate list
 * from config/portfolioIcons.js's PORTFOLIO_ICON_OPTIONS rather than a
 * shared one, since an account (ISA/GIA/SIPP/LISA/Trading — see
 * config/accountTypes.json) reads more like a wrapper/institution than a
 * pie's own asset mix, so the two sets are free to diverge as each area's
 * needs do. Extend as new use cases come up; IconPicker itself takes
 * whatever `icons` array it's given, so it doesn't need to change.
 *
 * Each value is the bare icon name (e.g. "bank2"), not the full
 * "bi bi-bank2" class — callers prefix it themselves (see IconBadge.jsx),
 * matching what's stored on the account.
 */
export const ACCOUNT_ICON_OPTIONS = [
  "bank2",
  "bank",
  "safe2-fill",
  "shield-lock-fill",
  "shield-fill-check",
  "briefcase-fill",
  "wallet2",
  "piggy-bank-fill",
  "cash-stack",
  "coin",
  "graph-up-arrow",
  "building",
  "building-check",
  "house-fill",
  "umbrella-fill",
  "gem",
  "award-fill",
  "flag-fill",
  "globe-americas",
  "person-badge-fill",
];

/** Rendered by IconBadge for any account whose `icon` is unset — every
 * account predates this feature, so most will hit this fallback until
 * edited. */
export const DEFAULT_ACCOUNT_ICON = "bank2";
