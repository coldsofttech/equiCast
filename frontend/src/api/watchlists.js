/**
 * @typedef {import("./accounts.js").Holding} Holding
 */

/**
 * @typedef {Object} WatchlistSystemEntry - one row of Global Markets',
 *   Top Winners', or Top Losers' content — computed live at request time
 *   by backend/watchlists/system_watchlists.py from each asset class's own
 *   published `catalog/<asset_class>.parquet` (see equicast_core.catalog),
 *   not a separate ingestion pipeline. Not a real Holding: no `id`
 *   (nothing to key a remove action off), no shares/cost-basis fields.
 *   `current_price` is always this instrument's own native currency — a
 *   system watchlist has no single owner to convert it for.
 * @property {"fx"|"future"|"benchmark"|"stock"|"etf"} asset_class
 * @property {string} ticker
 * @property {string|null} name
 * @property {string|null} currency
 * @property {number|null} current_price
 * @property {number|null} change_1w_pct
 * @property {number|null} change_1m_pct
 * @property {number|null} [change_1y_pct] - Top Winners/Top Losers (and
 *   Your Top Winners/Your Top Losers, on a real Holding there — see
 *   `Watchlist.holdings`) only — the trailing 1-year CAGR those rankings
 *   use, as a percent. Never set on a Global Markets row.
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
 * @property {(Holding|WatchlistSystemEntry)[]} holdings - always present.
 *   `WatchlistSystemEntry` rows for "global-markets"/"top-winners"/
 *   "top-losers" (a Global Markets row can still have every field but
 *   `name`/`asset_class`/`ticker` `null`, if that instrument's own
 *   ingestion pipeline hasn't published it yet — never dropped). Real
 *   `Holding` rows (plus each one's own `change_1y_pct`) for
 *   "top-winners-accounts"/"top-losers-accounts" — the caller's own
 *   account/pie holdings that rank as a winner/loser, enriched the same
 *   way a custom watchlist's holdings are. Empty for any of the five
 *   system tabs with nothing currently qualifying, and for any custom
 *   watchlist with nothing added to it yet.
 */

/**
 * GET /api/watchlists/ — see backend/watchlists/views.py's
 * WatchlistListView.get. Returns the five system watchlists (in a fixed
 * order, each computed live — see `Watchlist.holdings`) followed by the
 * caller's own custom ones, each nested with its enriched real holdings —
 * one fetch for the whole tabbed panel.
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
