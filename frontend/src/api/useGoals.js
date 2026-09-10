import { useEffect, useState } from "react";
import { useApi } from "./useApi.js";
import { listGoals } from "./goals.js";
import {
  readCachedGoals,
  writeCachedGoals,
  clearCachedGoals as deleteCachedGoals,
} from "../utils/goalsCache.js";

/** In-flight GET /goals/, shared across every concurrent mount (Dashboard + GoalsListPage on first load) so they collapse into one request instead of one each. */
let inFlight = null;

/** The last goals list this tab has seen (from the IndexedDB cache, a
 * GET /goals/, or a local create/update/delete) — same "render immediately
 * from memory on a second mount" reasoning as useAccounts.js's
 * memoryAccounts. `null` until the first mount resolves one of the above. */
let memoryGoals = null;

/**
 * Clears the cached goals list — call on sign-out alongside
 * clearCachedAccounts/clearCachedProfile so a different account signing in
 * on the same browser doesn't briefly render the previous user's goals.
 */
export function clearCachedGoals() {
  memoryGoals = null;
  return deleteCachedGoals();
}

/**
 * Same shared-cache pattern as useAccounts: DashboardPage and
 * GoalsListPage each mount this hook independently, so without a shared
 * cache both would hit GET /goals/ on every navigation between them.
 * Backed by IndexedDB (see utils/goalsCache.js) rather than sessionStorage,
 * so it also survives a tab close/reopen. `setGoals` has the same shape as
 * useState's own setter (value or updater function) and writes straight
 * back to the cache, so a create/edit/delete on either page — including the
 * client-side achieved-status sync (see pages/goals/goalFinancials.js's
 * useGoalAchievementSync) — is what the other page's next mount sees.
 *
 * @returns {{ goals: import("./goals.js").Goal[], isLoading: boolean, error: string | null, setGoals: (update: import("./goals.js").Goal[] | ((current: import("./goals.js").Goal[]) => import("./goals.js").Goal[])) => void }}
 */
export function useGoals() {
  const api = useApi();
  const [goals, setGoalsState] = useState(memoryGoals ?? []);
  const [isLoading, setIsLoading] = useState(memoryGoals == null);
  const [error, setError] = useState(null);

  const setGoals = (update) => {
    setGoalsState((current) => {
      const next = typeof update === "function" ? update(current) : update;
      memoryGoals = next;
      writeCachedGoals(next);
      return next;
    });
  };

  useEffect(() => {
    if (memoryGoals != null) return undefined;

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    (async () => {
      try {
        const cached = await readCachedGoals();
        if (cancelled) return;
        if (cached) {
          memoryGoals = cached;
          setGoalsState(cached);
          return;
        }

        if (!inFlight) {
          inFlight = listGoals(api).finally(() => {
            inFlight = null;
          });
        }
        const result = await inFlight;
        if (!cancelled) {
          memoryGoals = result;
          setGoalsState(result);
          writeCachedGoals(result);
        }
      } catch (err) {
        if (!cancelled) setError(err.message ?? "Couldn't load your goals.");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [api]);

  return { goals, isLoading, error, setGoals };
}
