import { useEffect, useState } from "react";

/**
 * Tracks the browser's own connectivity state (`navigator.onLine`,
 * updated live via the `online`/`offline` window events) — Topbar uses
 * this to show a slim banner instead of blocking the whole app, since
 * every page's fetches already cache their last response in IndexedDB
 * (priceCache.js, eventsCache.js, sessionCache.js, ...), so a signed-in
 * visitor can keep reading that cached data while offline.
 *
 * `navigator.onLine` only reflects whether the device has *a* network
 * interface up, not whether equiCast's own API is actually reachable
 * through it — a captive portal or a dead router the OS still considers
 * "connected" can still read `true` here. That reachable-network-but-
 * unreachable-API case is what ServiceUnavailablePage (a different,
 * per-page path — see isServiceUnavailableError.js) covers instead; this
 * hook only ever answers "does the device think it's online at all."
 */
function useOnlineStatus() {
  const [isOnline, setIsOnline] = useState(() =>
    typeof navigator === "undefined" ? true : navigator.onLine
  );

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return isOnline;
}

export default useOnlineStatus;
