/**
 * @typedef {Object} UserProfile
 * @property {string} user_id
 * @property {string} default_currency
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
