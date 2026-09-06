/**
 * Shared IndexedDB plumbing (one "equicast-cache" database) behind
 * priceCache.js/profileCache.js/metricsCache.js/accountsCache.js. IndexedDB
 * over sessionStorage: it survives a tab close/reopen (a user coming back
 * later shouldn't re-hit the API just because they closed the tab), and its
 * per-origin quota is far above sessionStorage's ~5-10MB, so caching many
 * tickers/ranges/accounts across a session can't realistically fill it.
 *
 * Two object stores, for two different freshness models:
 *  - "holdings" — price/profile/metrics entries, keyed by the caller's own
 *    namespaced key ("...:prices:...", "...:profile", "...:metrics" — see
 *    each cache module's own `*CacheKey`). The backend's published market
 *    data only changes once a day (the ingestion pipelines run on a daily
 *    cadence, see packages/stock|etf|fx's CLIs), so `readCachedValue`/
 *    `writeCachedValue` wrap entries with the calendar date they were
 *    written and treat anything from an earlier day as a miss.
 *  - "accounts" — the signed-in user's accounts list (see accountsCache.js).
 *    Unlike market data, this has no daily refresh cadence of its own: it's
 *    mutated directly by the user (create/update/delete), so it's kept
 *    fresh by the caller overwriting it on every mutation rather than by a
 *    calendar-day expiry — `readAccountsValue`/`writeAccountsValue`/
 *    `deleteAccountsValue` store/return the raw value, undated.
 *
 * Every read/write here is best-effort: IndexedDB can be unavailable (a
 * test environment, a browser/private-mode without it) or a call can fail
 * for any other reason, and none of that should ever break the page — a
 * read failure is just a cache miss, a write failure is just "nothing got
 * cached this time".
 */

const DB_NAME = "equicast-cache";
const DB_VERSION = 2;
const HOLDINGS_STORE_NAME = "holdings";
const ACCOUNTS_STORE_NAME = "accounts";

function openDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(HOLDINGS_STORE_NAME)) db.createObjectStore(HOLDINGS_STORE_NAME);
      if (!db.objectStoreNames.contains(ACCOUNTS_STORE_NAME)) db.createObjectStore(ACCOUNTS_STORE_NAME);
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
export async function readCachedValue(key) {
  try {
    const db = await openDb();
    const entry = await new Promise((resolve, reject) => {
      const request = db.transaction(HOLDINGS_STORE_NAME, "readonly").objectStore(HOLDINGS_STORE_NAME).get(key);
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
export async function writeCachedValue(key, value) {
  try {
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(HOLDINGS_STORE_NAME, "readwrite");
      tx.objectStore(HOLDINGS_STORE_NAME).put({ value, cachedDate: todayKey() }, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  } catch {
    // Best-effort — see module docstring.
  }
}

/**
 * @param {string} key
 * @returns {Promise<unknown|null>} `null` on a cache miss or any failure.
 */
export async function readAccountsValue(key) {
  try {
    const db = await openDb();
    const value = await new Promise((resolve, reject) => {
      const request = db.transaction(ACCOUNTS_STORE_NAME, "readonly").objectStore(ACCOUNTS_STORE_NAME).get(key);
      request.onsuccess = () => resolve(request.result ?? null);
      request.onerror = () => reject(request.error);
    });
    db.close();
    return value;
  } catch {
    return null;
  }
}

/**
 * @param {string} key
 * @param {unknown} value
 * @returns {Promise<void>}
 */
export async function writeAccountsValue(key, value) {
  try {
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(ACCOUNTS_STORE_NAME, "readwrite");
      tx.objectStore(ACCOUNTS_STORE_NAME).put(value, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  } catch {
    // Best-effort — see module docstring.
  }
}

/**
 * @param {string} key
 * @returns {Promise<void>}
 */
export async function deleteAccountsValue(key) {
  try {
    const db = await openDb();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(ACCOUNTS_STORE_NAME, "readwrite");
      tx.objectStore(ACCOUNTS_STORE_NAME).delete(key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  } catch {
    // Best-effort — see module docstring.
  }
}
