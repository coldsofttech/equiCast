import { useEffect, useState } from "react";
import { useApi } from "./useApi.js";
import { listAccounts } from "./accounts.js";
import { readCache, writeCache, clearCache } from "./sessionCache.js";

const CACHE_KEY = "ec_accounts";

/** In-flight GET /accounts/, shared across every concurrent mount (Dashboard + AccountsListPage on first load) so they collapse into one request instead of one each. */
let inFlight = null;

/**
 * Clears the cached accounts list — call on sign-out alongside
 * clearCachedProfile (see useCurrentUser.js) so a different account signing
 * in on the same tab doesn't briefly render the previous user's accounts.
 */
export function clearCachedAccounts() {
  clearCache(CACHE_KEY);
}

/**
 * Same session-cached pattern as useCurrentUser: DashboardPage and
 * AccountsListPage each mount this hook independently, so without a shared
 * cache both would hit GET /accounts/ on every navigation between them.
 * `setAccounts` has the same shape as useState's own setter (value or
 * updater function) and writes straight back to the session cache, so a
 * create/edit/delete on either page is what the other page's next mount
 * sees — no separate invalidation step.
 *
 * @returns {{ accounts: import("./accounts.js").Account[], isLoading: boolean, error: string | null, setAccounts: (update: import("./accounts.js").Account[] | ((current: import("./accounts.js").Account[]) => import("./accounts.js").Account[])) => void }}
 */
export function useAccounts() {
  const api = useApi();
  const [accounts, setAccountsState] = useState(() => readCache(CACHE_KEY) ?? []);
  const [isLoading, setIsLoading] = useState(() => !readCache(CACHE_KEY));
  const [error, setError] = useState(null);

  const setAccounts = (update) => {
    setAccountsState((current) => {
      const next = typeof update === "function" ? update(current) : update;
      writeCache(CACHE_KEY, next);
      return next;
    });
  };

  useEffect(() => {
    if (readCache(CACHE_KEY)) return undefined;

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    if (!inFlight) {
      inFlight = listAccounts(api).finally(() => {
        inFlight = null;
      });
    }

    inFlight
      .then((result) => {
        if (!cancelled) {
          setAccountsState(result);
          writeCache(CACHE_KEY, result);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? "Couldn't load your accounts.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [api]);

  return { accounts, isLoading, error, setAccounts };
}
