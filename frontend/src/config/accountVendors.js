/**
 * Suggested account vendors/platforms (GitHub equicast-support#171) —
 * offered as a `<datalist>` for `AccountForm`'s free-text `vendor` field
 * (see backend/accounts/views.py's OPTIONAL_CREATE_FIELDS/UPDATABLE_FIELDS),
 * the same "curated options, but free text wins" pattern
 * config/accountIcons.js's ACCOUNT_ICON_OPTIONS uses for `icon` — a picker
 * would be too rigid here since a user's actual broker/platform may not be
 * one of these, but a `<datalist>` still cuts down on inconsistent spelling
 * for the common ones (e.g. "trading212" vs "Trading 212" vs "Trading212").
 * Purely a UX nicety: nothing here is validated against server-side (the
 * stored value is whatever free text the user typed or picked).
 */
export const ACCOUNT_VENDOR_SUGGESTIONS = [
  "Trading212",
  "Chip",
  "Vanguard",
  "Hargreaves Lansdown",
  "AJ Bell",
  "Interactive Investor",
  "Freetrade",
  "InvestEngine",
  "Nutmeg",
  "Moneybox",
  "Fidelity",
  "Charles Schwab",
  "Robinhood",
  "eToro",
  "Revolut",
];
