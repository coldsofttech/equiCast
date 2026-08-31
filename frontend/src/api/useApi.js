import { useAuth0 } from "@auth0/auth0-react";
import { useCallback } from "react";
import { apiFetch } from "./client.js";

/**
 * Binds Auth0's `getAccessTokenSilently` into `apiFetch` so components can
 * just call `api("/identity/me/")` without threading a token through
 * themselves. Must be used inside an Auth0Provider (i.e. below
 * RequireAuth, where isAuthenticated is already known true) — calling it
 * higher up would attempt token retrieval before there's a session to get
 * one from.
 *
 * @returns {(path: string, options?: import("./client.js").ApiFetchOptions) => Promise<unknown>}
 */
export function useApi() {
  const { getAccessTokenSilently } = useAuth0();

  return useCallback(
    (path, options = {}) => apiFetch(path, { ...options, getAccessToken: getAccessTokenSilently }),
    [getAccessTokenSilently]
  );
}
