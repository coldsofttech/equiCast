import { useEffect, useState } from "react";
import { useApi } from "./useApi.js";
import { listAccounts } from "./accounts.js";
import {
  readCachedAccounts,
  writeCachedAccounts,
  clearCachedAccounts as deleteCachedAccounts,
} from "../utils/accountsCache.js";

/** In-flight GET /accounts/, shared across every concurrent mount (Dashboard + AccountsListPage on first load) so they collapse into one request instead of one each. */
let inFlight = null;

/** The last accounts list this tab has seen (from the IndexedDB cache, a
 * GET /accounts/, or a local create/update/delete) — lets a mount after the
 * first (e.g. Dashboard mounting right after AccountsListPage) render
 * immediately from memory instead of round-tripping IndexedDB again, which
 * unlike sessionStorage's synchronous reads is always at least one
 * microtask away. `null` until the first mount resolves one of the above. */
let memoryAccounts = null;

/**
 * Clears the cached accounts list — call on sign-out alongside
 * clearCachedProfile (see useCurrentUser.js) so a different account signing
 * in on the same browser doesn't briefly render the previous user's
 * accounts.
 */
export function clearCachedAccounts() {
  memoryAccounts = null;
  return deleteCachedAccounts();
}

/**
 * Same shared-cache pattern as useCurrentUser: DashboardPage and
 * AccountsListPage each mount this hook independently, so without a shared
 * cache both would hit GET /accounts/ on every navigation between them.
 * Backed by IndexedDB (see utils/accountsCache.js) rather than
 * sessionStorage, so it also survives a tab close/reopen. `setAccounts` has
 * the same shape as useState's own setter (value or updater function) and
 * writes straight back to the cache, so a create/edit/delete on either page
 * is what the other page's next mount sees — no separate invalidation step.
 *
 * @returns {{ accounts: import("./accounts.js").Account[], isLoading: boolean, error: string | null, errorStatus: number | null, setAccounts: (update: import("./accounts.js").Account[] | ((current: import("./accounts.js").Account[]) => import("./accounts.js").Account[])) => void }}
 */
export function useAccounts() {
  const api = useApi();
  const [accounts, setAccountsState] = useState(memoryAccounts ?? []);
  const [isLoading, setIsLoading] = useState(memoryAccounts == null);
  const [error, setError] = useState(null);
  // The failed request's real HTTP status (null for a network failure with
  // no response at all) — kept alongside `error`'s plain message so a
  // caller can tell a genuine service-level failure (see
  // isServiceUnavailableError.js) from an ordinary 4xx without this hook
  // needing to know anything about how that distinction gets rendered.
  const [errorStatus, setErrorStatus] = useState(null);

  const setAccounts = (update) => {
    setAccountsState((current) => {
      const next = typeof update === "function" ? update(current) : update;
      memoryAccounts = next;
      writeCachedAccounts(next);
      return next;
    });
  };

  useEffect(() => {
    if (memoryAccounts != null) return undefined;

    let cancelled = false;
    setIsLoading(true);
    setError(null);
    setErrorStatus(null);

    (async () => {
      try {
        const cached = await readCachedAccounts();
        if (cancelled) return;
        if (cached) {
          memoryAccounts = cached;
          setAccountsState(cached);
          return;
        }

        if (!inFlight) {
          inFlight = listAccounts(api).finally(() => {
            inFlight = null;
          });
        }
        const result = await inFlight;
        if (!cancelled) {
          memoryAccounts = result;
          setAccountsState(result);
          writeCachedAccounts(result);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message ?? "Couldn't load your accounts.");
          setErrorStatus(err.status ?? null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [api]);

  return { accounts, isLoading, error, errorStatus, setAccounts };
}
