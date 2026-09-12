/**
 * The fixed set of goal purposes (see equicast_core.goals.PURPOSE_CHOICES /
 * backend/goals/views.py's `_validate_purpose`) plus their display label,
 * bootstrap-icons name (bare, e.g. "house-heart" — see IconBadge.jsx) and
 * Badge tone — a closed enum, so a static lookup map (same shape as
 * AssetTypeBadge.jsx's ASSET_TYPE_LABELS/ASSET_TYPE_BADGE_TONES) rather
 * than the user-editable IconPicker/config-json pattern account icons use.
 */
export const GOAL_PURPOSE_LABELS = {
  buy_home: "Buy a home",
  buy_car: "Buy a car",
  holiday: "Holiday",
  emergency_fund: "Emergency fund",
  retirement: "Retirement",
  education: "Education",
  wedding: "Wedding",
  other: "Other",
};

export const GOAL_PURPOSE_ICONS = {
  buy_home: "house-heart-fill",
  buy_car: "car-front-fill",
  holiday: "airplane-fill",
  emergency_fund: "umbrella-fill",
  retirement: "piggy-bank-fill",
  education: "mortarboard-fill",
  wedding: "gem",
  other: "flag-fill",
};

export const GOAL_PURPOSE_BADGE_TONES = {
  buy_home: "success",
  buy_car: "info",
  holiday: "warning",
  emergency_fund: "danger",
  retirement: "purple",
  education: "accent",
  wedding: "purple",
  other: "neutral",
};

/** Ordered for `<select>`/picker rendering — GoalForm.jsx iterates this
 * rather than `Object.keys(GOAL_PURPOSE_LABELS)` so the order is explicit
 * and stable regardless of key-insertion order. */
export const PURPOSE_CHOICES = [
  "buy_home",
  "buy_car",
  "holiday",
  "emergency_fund",
  "retirement",
  "education",
  "wedding",
  "other",
];

/** Rendered by IconBadge for a purpose that somehow isn't in
 * GOAL_PURPOSE_ICONS (shouldn't happen — purpose is server-validated
 * against the same enum — but IconBadge always wants a fallback). */
export const DEFAULT_GOAL_ICON = GOAL_PURPOSE_ICONS.other;
