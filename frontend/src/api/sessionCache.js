/**
 * Thin sessionStorage read/write/clear helpers, tolerant of storage being
 * unavailable (private browsing, storage disabled) — every call is a no-op
 * on failure rather than throwing, since caching here is a best-effort
 * optimization (skip a round trip), never a source of truth.
 */

export function readCache(key) {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function writeCache(key, value) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // ignore — see file doc
  }
}

export function clearCache(key) {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // ignore — see file doc
  }
}
