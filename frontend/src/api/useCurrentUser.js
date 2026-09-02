import { useEffect, useState } from "react";
import { useApi } from "./useApi.js";
import { getMe } from "./identity.js";
import { readCache, writeCache, clearCache } from "./sessionCache.js";

const CACHE_KEY = "ec_profile";

/** In-flight GET /identity/me/, shared across every concurrent mount (e.g. Topbar + a page both mounting on first load) so they collapse into one request instead of one each. */
let inFlight = null;

/**
 * Clears the cached profile — call on sign-out. sessionStorage survives the
 * Auth0 logout/login redirect round trip (same tab, same session), so
 * without this a different account signing back in on the same tab would
 * briefly render the previous user's cached default_currency.
 */
export function clearCachedProfile() {
  clearCache(CACHE_KEY);
}

/**
 * Fetches the caller's profile once per tab session and serves every other
 * mount of this hook (Topbar, AccountsListPage, DashboardPage, ... each
 * call it independently) from sessionStorage instead of hitting
 * GET /identity/me/ again. `setProfile` writes straight back to the cache
 * too, so a save from SettingsModal is what every later mount sees.
 *
 * @returns {{ profile: import("./identity.js").UserProfile | null, isLoading: boolean, error: string | null, setProfile: (profile: import("./identity.js").UserProfile) => void }}
 */
export function useCurrentUser() {
  const api = useApi();
  const [profile, setProfileState] = useState(() => readCache(CACHE_KEY));
  const [isLoading, setIsLoading] = useState(() => !readCache(CACHE_KEY));
  const [error, setError] = useState(null);

  const setProfile = (next) => {
    setProfileState(next);
    writeCache(CACHE_KEY, next);
  };

  useEffect(() => {
    if (readCache(CACHE_KEY)) return undefined;

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    if (!inFlight) {
      inFlight = getMe(api).finally(() => {
        inFlight = null;
      });
    }

    inFlight
      .then((result) => {
        if (!cancelled) {
          setProfileState(result);
          writeCache(CACHE_KEY, result);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message ?? "Couldn't load your profile.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [api]);

  return { profile, isLoading, error, setProfile };
}
