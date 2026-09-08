/**
 * @typedef {import("./accounts.js").Holding} Holding
 */

/**
 * @typedef {Object} WatchlistSystemEntry - one row of a system watchlist's
 *   pre-built content (e.g. Global Markets — see
 *   equicast_watchlist.builder/writer and MarketDataClient.
 *   get_watchlist_entries). Not a real Holding: no `id` (nothing to key a
 *   remove action off), no shares/cost-basis fields. `current_price` is
 *   always this instrument's own native currency — a system watchlist has
 *   no single owner to convert it for.
 * @property {"fx"|"future"|"benchmark"} asset_class
 * @property {string} ticker
 * @property {string} symbol
 * @property {string|null} name
 * @property {string|null} currency
 * @property {number|null} current_price
 * @property {number|null} change_1w_pct
 * @property {number|null} change_1m_pct
 * @property {string} last_updated
 * @property {string} source
 */

/**
 * @typedef {Object} Watchlist
 * @property {string} id
 * @property {string} name
 * @property {string} [description]
 * @property {"system"|"custom"} type - "system" for one of the five fixed
 *   defaults (see backend/watchlists/views.py's SYSTEM_WATCHLISTS — not
 *   user-editable, no `description`/`created_at`/`updated_at`), "custom"
 *   for one of the caller's own (up to MAX_WATCHLISTS, currently 5).
 * @property {(Holding|WatchlistSystemEntry)[]} holdings - always present;
 *   `WatchlistSystemEntry` rows for a system watchlist that's been built
 *   (today: just "global-markets" — see backend/watchlists/views.py's
 *   `_SYSTEM_WATCHLIST_STORAGE_KEYS`), empty for every other system
 *   watchlist (population is separate, not-yet-built work) and for any
 *   custom watchlist with nothing added to it yet.
 */

/**
 * GET /api/watchlists/ — see backend/watchlists/views.py's
 * WatchlistListView.get. Returns the five system watchlists (in a fixed
 * order — "global-markets" nested with its `WatchlistSystemEntry` rows,
 * the rest still `holdings: []`) followed by the caller's own custom ones,
 * each nested with its enriched real holdings — one fetch for the whole
 * tabbed panel.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @returns {Promise<Watchlist[]>}
 */
export function listWatchlists(api) {
  return /** @type {Promise<Watchlist[]>} */ (api("/watchlists/"));
}

/**
 * GET /api/watchlists/<id>/ — custom watchlists only, see
 * WatchlistDetailView's docstring; there's no S3-backed row for a system
 * watchlist to fetch by id.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} watchlistId
 * @returns {Promise<Watchlist>}
 */
export function getWatchlist(api, watchlistId) {
  return /** @type {Promise<Watchlist>} */ (api(`/watchlists/${watchlistId}/`));
}

/**
 * POST /api/watchlists/ — always creates a "custom" watchlist; 409s once
 * the caller already has MAX_WATCHLISTS (5).
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {{ name: string, description: string }} data
 * @returns {Promise<Watchlist>}
 */
export function createWatchlist(api, data) {
  return /** @type {Promise<Watchlist>} */ (api("/watchlists/", { method: "POST", body: data }));
}

/**
 * PATCH /api/watchlists/<id>/ — only `name`/`description` are updatable.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} watchlistId
 * @param {Partial<{ name: string, description: string }>} fields
 * @returns {Promise<Watchlist>}
 */
export function updateWatchlist(api, watchlistId, fields) {
  return /** @type {Promise<Watchlist>} */ (
    api(`/watchlists/${watchlistId}/`, { method: "PATCH", body: fields })
  );
}

/**
 * DELETE /api/watchlists/<id>/ — `force: true` cascades through the
 * watchlist's holdings; without it, a non-empty watchlist 409s.
 *
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {string} watchlistId
 * @param {{ force?: boolean }} [options]
 * @returns {Promise<null>}
 */
export function deleteWatchlist(api, watchlistId, { force = false } = {}) {
  const query = force ? "?force=true" : "";
  return /** @type {Promise<null>} */ (
    api(`/watchlists/${watchlistId}/${query}`, { method: "DELETE" })
  );
}
