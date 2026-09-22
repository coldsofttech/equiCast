/**
 * @typedef {Object} UserProfile
 * @property {string} user_id
 * @property {string} default_currency
 * @property {"AVERAGE"|"TRANSACTION"} transaction_type
 * @property {string[]} fx_warmup_currencies - currencies the login-time FX
 *   warm-up pairs against `default_currency` (see utils/fxWarmup.js and
 *   GitHub issue #149) — user-editable in Settings, defaults to `["GBP",
 *   "USD", "EUR"]` on first login.
 * @property {"UK"} tax_residency - GitHub issue #94. v1 tax logic is
 *   UK-only, so "UK" is the only accepted value for now — defaults to it
 *   on first login.
 * @property {"NONE"|"BASIC"|"HIGHER"|"ADDITIONAL"} income_tax_band - GitHub
 *   issue #94. Self-declared UK income tax band ("NONE" = non-taxpayer,
 *   below the personal allowance) — defaults to "BASIC" on first login.
 * @property {Record<string, number>} [dividend_allowance_used_by_tax_year] -
 *   GitHub issue #212. How much of the £500 UK dividend allowance has been
 *   consumed, keyed by "YYYY-YY" tax year label (e.g. "2026-27") — written
 *   only by the backend as taxable (GIA) DIVIDEND transactions are
 *   created/edited/deleted/rewound (see backend/transactions/views.py's
 *   _persist_dividend_allowance/_reverse_dividend_allowance), never
 *   directly by the user. Read-only here — see
 *   pages/dividendTax/dividendTaxFinancials.js.
 * @property {Record<string, number>} [dividend_tax_paid_by_tax_year] -
 *   GitHub issue #212's follow-up. The income-tax-band-rate UK dividend tax
 *   actually paid (never the foreign withholding amount, a separate
 *   already-shown-per-holding concept), keyed the same way as
 *   dividend_allowance_used_by_tax_year and written alongside it by the
 *   same backend paths. Read-only here.
 */

/**
 * GET /api/identity/me/ — see backend/identity/views.py's MeView. Creates
 * the caller's profile (default_currency "GBP") on first call if one
 * doesn't exist yet.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api - a
 *   bound client from useApi(), not the bare apiFetch (this always needs
 *   an access token).
 * @returns {Promise<UserProfile>}
 */
export function getMe(api) {
  return /** @type {Promise<UserProfile>} */ (api("/identity/me/"));
}

/**
 * PATCH /api/identity/me/ — see MeView.patch. `default_currency` must be
 * one of the codes in frontend/src/config/currencies.json (kept in sync
 * with the backend's own SUPPORTED_CURRENCIES; the frontend doesn't fetch
 * this list from the API to avoid a round trip for four static values).
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} defaultCurrency
 * @returns {Promise<UserProfile>}
 */
export function updateDefaultCurrency(api, defaultCurrency) {
  return /** @type {Promise<UserProfile>} */ (
    api("/identity/me/", { method: "PATCH", body: { default_currency: defaultCurrency } })
  );
}

/**
 * PATCH /api/identity/me/ — see MeView.patch. A single setting governing
 * how every holding across every one of the user's accounts/pies records
 * transactions (see equicast_core.transactions module docstring); 409s if
 * the user already has any transaction recorded anywhere.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {"AVERAGE"|"TRANSACTION"} transactionType
 * @returns {Promise<UserProfile>}
 */
export function updateTransactionType(api, transactionType) {
  return /** @type {Promise<UserProfile>} */ (
    api("/identity/me/", { method: "PATCH", body: { transaction_type: transactionType } })
  );
}

/**
 * PATCH /api/identity/me/ — see MeView.patch. The currencies the
 * login-time FX warm-up pairs against `default_currency` (see
 * utils/fxWarmup.js and GitHub issue #149) — each must be one of the
 * codes in frontend/src/config/currencies.json, same as
 * `updateDefaultCurrency`.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string[]} currencies
 * @returns {Promise<UserProfile>}
 */
export function updateFxWarmupCurrencies(api, currencies) {
  return /** @type {Promise<UserProfile>} */ (
    api("/identity/me/", { method: "PATCH", body: { fx_warmup_currencies: currencies } })
  );
}

/**
 * PATCH /api/identity/me/ — see MeView.patch. GitHub issue #94; v1 tax
 * logic is UK-only, so "UK" is the only accepted value for now.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {"UK"} taxResidency
 * @returns {Promise<UserProfile>}
 */
export function updateTaxResidency(api, taxResidency) {
  return /** @type {Promise<UserProfile>} */ (
    api("/identity/me/", { method: "PATCH", body: { tax_residency: taxResidency } })
  );
}

/**
 * PATCH /api/identity/me/ — see MeView.patch. GitHub issue #94 — a
 * self-declared UK income tax band, always per-user (never
 * household-pooled).
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {"NONE"|"BASIC"|"HIGHER"|"ADDITIONAL"} incomeTaxBand
 * @returns {Promise<UserProfile>}
 */
export function updateIncomeTaxBand(api, incomeTaxBand) {
  return /** @type {Promise<UserProfile>} */ (
    api("/identity/me/", { method: "PATCH", body: { income_tax_band: incomeTaxBand } })
  );
}

/**
 * DELETE /api/identity/me/ — see MeView.delete (GitHub issue #158).
 * Permanently deletes every equicast-owned record for the caller (profile,
 * accounts, pies, goals, watchlists, holdings, transactions). Their Auth0
 * login itself is untouched — v1 scope, see the issue — so nothing stops
 * them signing up again afterward; the caller is responsible for logging
 * them out client-side once this resolves, since staying signed in would
 * just re-create an empty profile on the next `getMe` call.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @returns {Promise<null>}
 */
export function deleteAccount(api) {
  return /** @type {Promise<null>} */ (api("/identity/me/", { method: "DELETE" }));
}
