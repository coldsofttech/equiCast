import { useEffect, useRef } from "react";
import { updateGoal } from "../../api/goals.js";
import { computeHoldingValuation, summarizeHoldingValuations } from "../holdingValuation.js";

/**
 * A goal's live progress, computed entirely client-side from the already-
 * cached accounts tree (see useAccounts) — the backend never computes or
 * stores this (see api/goals.js's `Goal` typedef). Resolves `goal.account_ids`/
 * `goal.pie_ids` against `accounts`, flattens every matched account's direct
 * holdings plus every matched pie's holdings (same flatten idiom
 * AccountCard.jsx uses for one account) into one list, then runs the same
 * `computeHoldingValuation`/`summarizeHoldingValuations` pair every other
 * page uses for a "current value" total — each holding's `current_price`/
 * `invested` are already converted server-side to the user's
 * `default_currency` (see api/accounts.js's `Holding` typedef), so no FX
 * conversion happens here.
 *
 * A pie belonging to an account that's *also* mapped to this goal is only
 * counted once (via the account's own flattened holdings) — the backend
 * rejects that mapping combination up front (see backend/goals/views.py's
 * `_validate_mapping`), but `countedPieIds` guards against double-counting
 * defensively anyway, in case a goal loaded from a stale cache predates a
 * mapping fix.
 *
 * @param {import("../../api/goals.js").Goal} goal
 * @param {import("../../api/accounts.js").Account[]} accounts
 * @returns {{ currentValue: number, target: number, progressPct: number, isAchieved: boolean }}
 */
export function computeGoalProgress(goal, accounts) {
  const accountIds = new Set(goal.account_ids ?? []);
  const pieIds = new Set(goal.pie_ids ?? []);
  const countedPieIds = new Set();
  const holdings = [];

  for (const account of accounts) {
    const pies = account.pies ?? [];
    if (accountIds.has(account.id)) {
      holdings.push(...(account.holdings ?? []));
      for (const pie of pies) {
        holdings.push(...(pie.holdings ?? []));
        countedPieIds.add(pie.id);
      }
    }
    for (const pie of pies) {
      if (pieIds.has(pie.id) && !countedPieIds.has(pie.id)) {
        holdings.push(...(pie.holdings ?? []));
        countedPieIds.add(pie.id);
      }
    }
  }

  const valuations = holdings.map(computeHoldingValuation);
  const { currentValue } = summarizeHoldingValuations(holdings, valuations);
  const target = Number(goal.target_amount) || 0;
  const progressPct = target > 0 ? (currentValue / target) * 100 : 0;
  const isAchieved = target > 0 && currentValue >= target;
  return { currentValue, target, progressPct, isAchieved };
}

/**
 * Watches `goals`/`accounts` (both already loaded by the caller — this
 * fires no fetch of its own) and, the instant an `active` goal's
 * `computeGoalProgress` crosses its target, PATCHes it to `status:
 * "achieved"` once and folds the result back into the shared cache via
 * `setGoals` (see useGoals) — so the flip persists and every mounted
 * consumer (GoalsListPage, DashboardPage) sees it without a refetch.
 *
 * Used by both GoalsListPage and DashboardPage; `attemptedRef` scopes the
 * once-per-mount guard to this hook instance, so two mounts racing the same
 * PATCH is a harmless idempotent double-write rather than a bug.
 *
 * @param {import("../../api/goals.js").Goal[]} goals
 * @param {import("../../api/accounts.js").Account[]} accounts
 * @param {(path: string, options?: object) => Promise<unknown>} api
 * @param {(update: import("../../api/goals.js").Goal[] | ((current: import("../../api/goals.js").Goal[]) => import("../../api/goals.js").Goal[])) => void} setGoals
 */
export function useGoalAchievementSync(goals, accounts, api, setGoals) {
  const attemptedRef = useRef(new Set());

  useEffect(() => {
    for (const goal of goals) {
      if (goal.status !== "active") continue;
      if (attemptedRef.current.has(goal.id)) continue;
      if (!computeGoalProgress(goal, accounts).isAchieved) continue;

      attemptedRef.current.add(goal.id);
      updateGoal(api, goal.id, { status: "achieved" })
        .then((updated) => {
          setGoals((current) => current.map((g) => (g.id === updated.id ? updated : g)));
        })
        .catch(() => {
          // Leave it un-flipped locally; the next render where progress
          // still qualifies (goals/accounts unchanged won't re-run this
          // effect, but a later mutation will) retries.
          attemptedRef.current.delete(goal.id);
        });
    }
  }, [goals, accounts, api, setGoals]);
}
