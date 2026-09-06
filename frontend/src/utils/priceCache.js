/**
 * A same-day IndexedDB cache for GET .../prices/ and GET .../profile/
 * responses (see api/market.js's getPrices/getProfile) — the backend's
 * published market data only changes once a day (the ingestion pipelines
 * run on a daily cadence, see packages/stock|etf|fx's CLIs), so every hit
 * for the same asset_class/symbol(/range) on the same calendar day can be
 * served from the browser instead of the API. IndexedDB over
 * sessionStorage: it survives a tab close/reopen within the same day (a
 * user re-visiting a holding later that day shouldn't re-hit the API just
 * because they closed the tab), and its per-origin quota is far above
 * sessionStorage's ~5-10MB, so caching many tickers/ranges across a session
 * can't realistically fill it.
 *
 * Every function here is best-effort: IndexedDB can be unavailable (a test
 * environment, a browser/private-mode without it) or a call can fail for
 * any other reason, and none of that should ever break the page — a read
 * failure is just a cache miss, a write failure is just "nothing got
 * cached this time".
 */

const DB_NAME = "equicast-price-cache";
const DB_VERSION = 1;
const STORE_NAME = "prices";

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE_NAME);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/** The browser's local calendar date ("YYYY-MM-DD") — a cached entry is
 * fresh only for the rest of this same local day. */
function todayKey() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * @param {string} key
 * @returns {Promise<unknown|null>} `null` on a cache miss, a stale (not
 *   from today) entry, or any failure.
 */
async function readCachedValue(key) {
  try {
    const db = await openDb();
    const entry = await new Promise((resolve, reject) => {
      const request = db.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).get(key);
      request.onsuccess = () => resolve(request.result ?? null);
      request.onerror = () => reject(request.error);
    });
    db.close();
    return entry && entry.cachedDate === todayKey() ? entry.value : null;
  } catch {
    return null;
  }
}

/**
 * @param {string} key
 * @param {unknown} value
 * @returns {Promise<void>}
 */
async function writeCachedValue(key, value) {
  try {
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, "readwrite");
      tx.objectStore(STORE_NAME).put({ value, cachedDate: todayKey() }, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  } catch {
    // Best-effort — see module docstring.
  }
}

/**
 * @param {string} assetClass
 * @param {string} symbol
 * @param {string} range
 * @returns {string}
 */
export function priceCacheKey(assetClass, symbol, range) {
  return `${assetClass.toLowerCase()}:${symbol.toUpperCase()}:prices:${range}`;
}

/**
 * @param {string} assetClass
 * @param {string} symbol
 * @returns {string}
 */
export function profileCacheKey(assetClass, symbol) {
  return `${assetClass.toLowerCase()}:${symbol.toUpperCase()}:profile`;
}

/**
 * @param {string} key - see priceCacheKey
 * @returns {Promise<import("../api/market.js").PriceSeries|null>} `null`
 *   on a cache miss, a stale (not from today) entry, or any failure.
 */
export function readCachedPrices(key) {
  return /** @type {Promise<import("../api/market.js").PriceSeries|null>} */ (readCachedValue(key));
}

/**
 * @param {string} key - see priceCacheKey
 * @param {import("../api/market.js").PriceSeries} series
 * @returns {Promise<void>}
 */
export function writeCachedPrices(key, series) {
  return writeCachedValue(key, series);
}

/**
 * @param {string} key - see profileCacheKey
 * @returns {Promise<import("../api/market.js").MarketProfile|null>} `null`
 *   on a cache miss, a stale (not from today) entry, or any failure.
 */
export function readCachedProfile(key) {
  return /** @type {Promise<import("../api/market.js").MarketProfile|null>} */ (readCachedValue(key));
}

/**
 * @param {string} key - see profileCacheKey
 * @param {import("../api/market.js").MarketProfile} profile
 * @returns {Promise<void>}
 */
export function writeCachedProfile(key, profile) {
  return writeCachedValue(key, profile);
}
