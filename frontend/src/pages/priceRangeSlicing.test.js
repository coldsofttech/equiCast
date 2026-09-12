import { describe, expect, it } from "vitest";
import { sliceForRange } from "./priceRangeSlicing.js";

function bar(date) {
  return { date, open: 1, high: 1, low: 1, close: 1 };
}

describe("sliceForRange", () => {
  const history = {
    daily: [bar("2026-01-01"), bar("2026-01-02"), bar("2026-01-03"), bar("2026-01-04"), bar("2026-01-05"), bar("2026-01-06")],
    weekly: [bar("2025-01-03"), bar("2025-06-06"), bar("2026-01-02")],
    monthly: [bar("2015-01-31"), bar("2023-06-30"), bar("2026-01-02")],
  };

  it("takes the last 5 daily bars for 5d, not a date cutoff", () => {
    const result = sliceForRange(history, "5d", new Date(2026, 0, 10));
    expect(result.map((b) => b.date)).toEqual([
      "2026-01-02",
      "2026-01-03",
      "2026-01-04",
      "2026-01-05",
      "2026-01-06",
    ]);
  });

  it("filters daily bars by a 1-month cutoff", () => {
    const result = sliceForRange(history, "1m", new Date(2026, 0, 10));
    // cutoff = 2025-12-10, so every seeded daily bar (all Jan 2026) is included.
    expect(result).toHaveLength(6);
  });

  it("covers a full year-to-date window even past 6 months, using Jan 1", () => {
    const laterInYear = { daily: [bar("2026-01-02"), bar("2026-08-01")] };
    const result = sliceForRange(laterInYear, "ytd", new Date(2026, 10, 15));
    expect(result.map((b) => b.date)).toEqual(["2026-01-02", "2026-08-01"]);
  });

  it("excludes prior-year rows from ytd", () => {
    const withPriorYear = { daily: [bar("2025-12-31"), bar("2026-01-02")] };
    const result = sliceForRange(withPriorYear, "ytd", new Date(2026, 5, 1));
    expect(result.map((b) => b.date)).toEqual(["2026-01-02"]);
  });

  it("filters the weekly segment by a 1-year cutoff for 1y", () => {
    const result = sliceForRange(history, "1y", new Date(2026, 0, 10));
    // cutoff = 2025-01-10, so the 2025-01-03 bar (before it) is excluded.
    expect(result.map((b) => b.date)).toEqual(["2025-06-06", "2026-01-02"]);
  });

  it("returns the whole weekly segment as-is for 2y", () => {
    const result = sliceForRange(history, "2y", new Date(2026, 0, 10));
    expect(result).toBe(history.weekly);
  });

  it("filters the monthly segment by a month-based cutoff for 3y/5y/10y", () => {
    const result = sliceForRange(history, "5y", new Date(2026, 0, 10));
    expect(result.map((b) => b.date)).toEqual(["2023-06-30", "2026-01-02"]);
  });

  it("returns the whole monthly segment as-is for max", () => {
    const result = sliceForRange(history, "max", new Date(2026, 0, 10));
    expect(result).toBe(history.monthly);
  });

  it("degrades to empty arrays for a null/undefined history", () => {
    expect(sliceForRange(null, "max")).toEqual([]);
    expect(sliceForRange(undefined, "1y")).toEqual([]);
  });

  it("clamps the day-of-month when the target month is shorter", () => {
    // Mar 31 minus 1 month should land on Feb 28 (2026 isn't a leap year),
    // not an invalid Feb 31 — exercised indirectly via the 1m cutoff.
    const feb = { daily: [bar("2026-02-27"), bar("2026-02-28"), bar("2026-03-01")] };
    const result = sliceForRange(feb, "1m", new Date(2026, 2, 31));
    expect(result.map((b) => b.date)).toEqual(["2026-02-28", "2026-03-01"]);
  });
});
