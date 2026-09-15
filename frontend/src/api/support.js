/**
 * POST /api/support/ — GitHub issue #246. Raises a ticket as a GitHub
 * issue in a private repo the user has no access to (see backend/support/
 * views.py's module docstring for why it's a separate private repo, not
 * the public equiCast one) — the response is a generic confirmation only,
 * never an issue URL/number to follow.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ category: "query"|"ticker-request"|"incorrect-data"|"other", description: string, ticker?: string }} data
 * @returns {Promise<{ detail: string }>}
 */
export function submitSupportRequest(api, data) {
  return /** @type {Promise<{ detail: string }>} */ (
    api("/support/", { method: "POST", body: data })
  );
}
