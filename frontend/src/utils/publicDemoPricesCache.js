/**
 * A same-day localStorage cache for GET /market/public/demo-prices/ (see
 * api/publicMarket.js's getPublicDemoPrices) — plain localStorage rather
 * than the IndexedDB store the rest of market_data's caches (priceCache.js
 * etc.) use: this is the landing page's one pre-login call, with a single,
 * tiny, fixed payload (3 tickers x ~1 month of daily bars), so there's no
 * need for IndexedDB's async API/larger quota here, and every page load
 * before sign-in (no session to persist anything else against) would
 * otherwise re-hit it.
 */

const STORAGE_KEY = "ec-public-demo-prices";

/** The browser's local calendar date ("YYYY-MM-DD") — a cached entry is
 * fresh only for the rest of this same local day, matching the daily
 * cadence the backend's own market data refreshes on. */
function todayKey() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * @returns {{tickers: import("../api/publicMarket.js").PublicDemoTicker[]}|null}
 *   `null` on a cache miss, a stale (not from today) entry, or any failure.
 */
export function readCachedDemoPrices() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const entry = JSON.parse(raw);
    return entry?.cachedDate === todayKey() ? entry.value : null;
  } catch {
    return null;
  }
}

/**
 * @param {{tickers: import("../api/publicMarket.js").PublicDemoTicker[]}} value
 */
export function writeCachedDemoPrices(value) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ value, cachedDate: todayKey() }));
  } catch {
    // Best-effort — storage can be unavailable (private browsing) or full;
    // the page just refetches next time.
  }
}
