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
