import { describe, expect, it } from "vitest";
import { computeGoalProgress } from "./goalFinancials.js";

function holding({ invested = 1000, shares = 10, currentPrice = 120 } = {}) {
  return { invested, no_of_shares: shares, current_price: currentPrice };
}

describe("computeGoalProgress", () => {
  it("sums a mapped account's direct and pie-nested holdings", () => {
    const accounts = [
      {
        id: "acc-1",
        holdings: [holding({ shares: 5, currentPrice: 100 })], // 500
        pies: [{ id: "pie-1", holdings: [holding({ shares: 5, currentPrice: 100 })] }], // 500
      },
    ];
    const goal = { account_ids: ["acc-1"], pie_ids: [], target_amount: 1000 };

    const progress = computeGoalProgress(goal, accounts);

    expect(progress.currentValue).toBe(1000);
    expect(progress.progressPct).toBe(100);
    expect(progress.isAchieved).toBe(true);
  });

  it("sums a mapped pie belonging to an unmapped account", () => {
    const accounts = [
      {
        id: "acc-1",
        holdings: [holding({ shares: 5, currentPrice: 100 })], // not mapped, excluded
        pies: [{ id: "pie-1", holdings: [holding({ shares: 2, currentPrice: 100 })] }], // 200
      },
    ];
    const goal = { account_ids: [], pie_ids: ["pie-1"], target_amount: 1000 };

    const progress = computeGoalProgress(goal, accounts);

    expect(progress.currentValue).toBe(200);
    expect(progress.isAchieved).toBe(false);
  });

  it("does not double-count a pie whose account is also mapped", () => {
    const accounts = [
      {
        id: "acc-1",
        holdings: [],
        pies: [{ id: "pie-1", holdings: [holding({ shares: 2, currentPrice: 100 })] }], // 200
      },
    ];
    const goal = { account_ids: ["acc-1"], pie_ids: ["pie-1"], target_amount: 1000 };

    const progress = computeGoalProgress(goal, accounts);

    expect(progress.currentValue).toBe(200);
  });

  it("ignores unmapped accounts/pies", () => {
    const accounts = [
      { id: "acc-1", holdings: [holding()], pies: [] },
      { id: "acc-2", holdings: [holding()], pies: [] },
    ];
    const goal = { account_ids: ["acc-2"], pie_ids: [], target_amount: 5000 };

    const progress = computeGoalProgress(goal, accounts);

    expect(progress.currentValue).toBe(1200);
  });

  it("returns zero progress for a goal with no mappings", () => {
    const accounts = [{ id: "acc-1", holdings: [holding()], pies: [] }];
    const goal = { account_ids: [], pie_ids: [], target_amount: 1000 };

    const progress = computeGoalProgress(goal, accounts);

    expect(progress.currentValue).toBe(0);
    expect(progress.progressPct).toBe(0);
    expect(progress.isAchieved).toBe(false);
  });
});
