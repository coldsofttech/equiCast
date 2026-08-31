import { useEffect, useState } from "react";
import { useApi } from "./useApi.js";
import { getMe } from "./identity.js";

/**
 * Fetches the caller's profile once on mount. This is the one real
 * end-to-end proof this phase has: Auth0 login -> access token ->
 * Authorization header -> Auth0JWTAuthentication -> DynamoDB
 * get_or_create_profile -> JSON back into React state.
 *
 * @returns {{ profile: import("./identity.js").UserProfile | null, isLoading: boolean, error: string | null }}
 */
export function useCurrentUser() {
  const api = useApi();
  const [profile, setProfile] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    setIsLoading(true);
    setError(null);
    getMe(api)
      .then((result) => {
        if (!cancelled) setProfile(result);
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

  return { profile, isLoading, error };
}
