import { describe, expect, it, vi } from "vitest";
import {
  formatDividendFrequency,
  formatPercent,
  formatPrice,
  formatRatio,
  resolveFxRate,
  rollupInstances,
  selectDividendHistory,
  selectUpcomingDividends,
  selectUpcomingDividendsInRange,
} from "./holdingFinancials.js";

describe("formatPrice", () => {
  it("formats a currency value to 2 decimal places", () => {
    const expected = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: "USD",
      currencyDisplay: "narrowSymbol",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(34.5);
    expect(formatPrice(34.5, "USD")).toBe(expected);
  });

  it("falls back to a plain number when currency is unknown", () => {
    expect(formatPrice(34.5, null)).toBe("34.50");
  });
});

describe("formatPercent", () => {
  it("scales a fraction to a percentage string", () => {
    expect(formatPercent(0.234)).toBe("23.4%");
  });

  it("keeps a negative fraction's sign", () => {
    expect(formatPercent(-0.08)).toBe("-8.0%");
  });

  it("returns null when unset", () => {
    expect(formatPercent(null)).toBeNull();
    expect(formatPercent(undefined)).toBeNull();
  });
});

describe("formatRatio", () => {
  it("formats a plain decimal ratio to 2 places by default", () => {
    expect(formatRatio(28.456)).toBe("28.46");
  });

  it("returns null when unset", () => {
    expect(formatRatio(null)).toBeNull();
    expect(formatRatio(undefined)).toBeNull();
  });
});

describe("rollupInstances", () => {
  it("sums shares/invested across mixed AVERAGE and TRANSACTION instances", () => {
    const instances = [
      { shares: 10, avgPriceNative: 100, invested: 1000 },
      { shares: 5, avgPriceNative: 200, invested: 1000 },
    ];
    const result = rollupInstances(instances, 150);
    expect(result.shares).toBe(15);
    expect(result.invested).toBe(2000);
    expect(result.currentValue).toBe(2250);
    expect(result.plValue).toBe(250);
    expect(result.plPct).toBeCloseTo(12.5);
  });

  it("returns null current value/P&L when the current price is unknown", () => {
    const result = rollupInstances([{ shares: 10, avgPriceNative: 100, invested: 1000 }], null);
    expect(result.currentValue).toBeNull();
    expect(result.plValue).toBeNull();
    expect(result.plPct).toBeNull();
  });
});

describe("resolveFxRate", () => {
  it("short-circuits to 1 when native and default currencies match", async () => {
    const api = vi.fn();
    await expect(resolveFxRate(api, "USD", "USD")).resolves.toBe(1);
    expect(api).not.toHaveBeenCalled();
  });

  it("returns null when either currency is unknown", async () => {
    const api = vi.fn();
    await expect(resolveFxRate(api, null, "USD")).resolves.toBeNull();
    expect(api).not.toHaveBeenCalled();
  });

  it("uses the direct pair's rate when published", async () => {
    const api = vi.fn().mockResolvedValue({ day_close: 0.79 });

    const rate = await resolveFxRate(api, "USD", "GBP");

    expect(api).toHaveBeenCalledWith("/market/fx/USDGBP/profile/");
    expect(rate).toBe(0.79);
  });

  it("falls back to the inverted pair, taking its reciprocal", async () => {
    const api = vi
      .fn()
      .mockRejectedValueOnce(new Error("404"))
      .mockResolvedValueOnce({ day_close: 1.25 });

    const rate = await resolveFxRate(api, "USD", "GBP");

    expect(api).toHaveBeenNthCalledWith(1, "/market/fx/USDGBP/profile/");
    expect(api).toHaveBeenNthCalledWith(2, "/market/fx/GBPUSD/profile/");
    expect(rate).toBeCloseTo(0.8);
  });

  it("resolves to null when neither pair is published", async () => {
    const api = vi.fn().mockRejectedValue(new Error("404"));

    await expect(resolveFxRate(api, "USD", "GBP")).resolves.toBeNull();
  });
});

describe("formatDividendFrequency", () => {
  it("maps each known backend cadence to a display label", () => {
    expect(formatDividendFrequency("weekly")).toBe("Weekly");
    expect(formatDividendFrequency("monthly")).toBe("Monthly");
    expect(formatDividendFrequency("quarterly")).toBe("Quarterly");
    expect(formatDividendFrequency("half_yearly")).toBe("Semi-annual");
    expect(formatDividendFrequency("yearly")).toBe("Annual");
    expect(formatDividendFrequency("irregular")).toBe("Irregular");
  });

  it("returns null for not_applicable and unset values", () => {
    expect(formatDividendFrequency("not_applicable")).toBeNull();
    expect(formatDividendFrequency(null)).toBeNull();
    expect(formatDividendFrequency(undefined)).toBeNull();
  });
});

describe("selectUpcomingDividends", () => {
  function isoDateDaysFromNow(days) {
    const date = new Date();
    date.setDate(date.getDate() + days);
    return date.toISOString().slice(0, 10);
  }

  function record(status, daysFromNow, overrides = {}) {
    return {
      ticker: "AAPL",
      currency: "USD",
      ex_dividend_date: isoDateDaysFromNow(daysFromNow),
      payment_date: null,
      price: 0.26,
      status,
      last_updated: "2026-08-30T09:00:00+00:00",
      source: status === "estimated" ? "equicast" : "yfinance",
      ...overrides,
    };
  }

  it("excludes paid (already-happened) records", () => {
    const dividends = [record("paid", -30), record("declared", 10)];
    expect(selectUpcomingDividends(dividends)).toEqual([dividends[1]]);
  });

  it("excludes records dated today or earlier", () => {
    const dividends = [record("declared", 0), record("declared", -1), record("estimated", 10)];
    expect(selectUpcomingDividends(dividends)).toEqual([dividends[2]]);
  });

  it("combines declared and estimated, sorted nearest first", () => {
    const dividends = [record("estimated", 90), record("declared", 10), record("estimated", 45)];
    expect(selectUpcomingDividends(dividends)).toEqual([dividends[1], dividends[2], dividends[0]]);
  });

  it("drops an estimated record on/before the declared record's ex-date", () => {
    // future.parquet and forecasting/dividends.parquet are independent
    // projections that can both target the same real-world payout - the
    // declared one must win rather than showing both.
    const declared = record("declared", 12);
    const overlappingEstimated = record("estimated", 10); // before the declared date
    const sameDateEstimated = record("estimated", 12); // same date as declared
    const laterEstimated = record("estimated", 100); // a genuinely later payout

    const result = selectUpcomingDividends([
      overlappingEstimated,
      sameDateEstimated,
      declared,
      laterEstimated,
    ]);

    expect(result).toEqual([declared, laterEstimated]);
  });

  it("caps at MAX_UPCOMING_DIVIDENDS (3), nearest first", () => {
    const dividends = [
      record("estimated", 400),
      record("estimated", 10),
      record("estimated", 100),
      record("estimated", 200),
    ];

    const result = selectUpcomingDividends(dividends);

    expect(result).toEqual([dividends[1], dividends[2], dividends[3]]);
  });

  it("returns an empty array when there's nothing upcoming", () => {
    const dividends = [record("paid", -30), record("paid", -10)];
    expect(selectUpcomingDividends(dividends)).toEqual([]);
  });

  it("returns every upcoming record uncapped when limit is Infinity", () => {
    const dividends = [
      record("estimated", 400),
      record("estimated", 10),
      record("estimated", 100),
      record("estimated", 200),
    ];

    const result = selectUpcomingDividends(dividends, Infinity);

    expect(result).toEqual([dividends[1], dividends[2], dividends[3], dividends[0]]);
  });
});

describe("selectUpcomingDividendsInRange", () => {
  function isoDateFromNow(days) {
    const date = new Date();
    date.setDate(date.getDate() + days);
    return date.toISOString().slice(0, 10);
  }

  function upcomingRecord(status, daysFromNow, overrides = {}) {
    return {
      ticker: "AAPL",
      currency: "USD",
      ex_dividend_date: isoDateFromNow(daysFromNow),
      payment_date: null,
      price: 0.26,
      status,
      last_updated: "2026-08-30T09:00:00+00:00",
      source: status === "estimated" ? "equicast" : "yfinance",
      ...overrides,
    };
  }

  it("includes upcoming records on/before the range cutoff", () => {
    const withinOneYear = upcomingRecord("estimated", 300);
    const overOneYearOut = upcomingRecord("estimated", 400);

    const result = selectUpcomingDividendsInRange([withinOneYear, overOneYearOut], "1y");

    expect(result).toEqual([withinOneYear]);
  });

  it("excludes paid and past records", () => {
    const dividends = [upcomingRecord("paid", -30), upcomingRecord("declared", 10)];
    expect(selectUpcomingDividendsInRange(dividends, "1y")).toEqual([dividends[1]]);
  });

  it("applies the same declared-wins dedup as selectUpcomingDividends", () => {
    const declared = upcomingRecord("declared", 12);
    const overlappingEstimated = upcomingRecord("estimated", 10);
    const laterEstimated = upcomingRecord("estimated", 100);

    const result = selectUpcomingDividendsInRange(
      [overlappingEstimated, declared, laterEstimated],
      "1y"
    );

    expect(result).toEqual([declared, laterEstimated]);
  });

  it("a wider range includes records a narrower one excludes", () => {
    const dividends = [upcomingRecord("estimated", 400), upcomingRecord("estimated", 1500)];

    expect(selectUpcomingDividendsInRange(dividends, "2y")).toEqual([dividends[0]]);
    expect(selectUpcomingDividendsInRange(dividends, "5y")).toEqual(dividends);
  });

  it("returns an empty array when nothing falls in range", () => {
    const dividends = [upcomingRecord("estimated", 1500)];
    expect(selectUpcomingDividendsInRange(dividends, "1y")).toEqual([]);
  });
});

describe("selectDividendHistory", () => {
  function isoDateYearsAgo(years) {
    const date = new Date();
    date.setFullYear(date.getFullYear() - years);
    return date.toISOString().slice(0, 10);
  }

  function paidRecord(yearsAgo, overrides = {}) {
    return {
      ticker: "AAPL",
      currency: "USD",
      ex_dividend_date: isoDateYearsAgo(yearsAgo),
      payment_date: null,
      price: 0.26,
      status: "paid",
      last_updated: "2026-08-30T09:00:00+00:00",
      source: "yfinance",
      ...overrides,
    };
  }

  it("excludes declared/estimated records", () => {
    const dividends = [
      paidRecord(0.5),
      { ...paidRecord(0.1), status: "declared" },
      { ...paidRecord(0.1), status: "estimated" },
    ];

    expect(selectDividendHistory(dividends, "max")).toEqual([dividends[0]]);
  });

  it("sorts ascending by ex-dividend date", () => {
    const older = paidRecord(2);
    const newer = paidRecord(0.5);

    expect(selectDividendHistory([newer, older], "max")).toEqual([older, newer]);
  });

  it("max returns every paid record, regardless of age", () => {
    const dividends = [paidRecord(1), paidRecord(9)];
    expect(selectDividendHistory(dividends, "max")).toEqual(
      [...dividends].sort((a, b) => a.ex_dividend_date.localeCompare(b.ex_dividend_date))
    );
  });

  it("trims to the given range", () => {
    const withinOneYear = paidRecord(0.5);
    const overOneYearAgo = paidRecord(1.5);

    const result = selectDividendHistory([withinOneYear, overOneYearAgo], "1y");

    expect(result).toEqual([withinOneYear]);
  });

  it("returns an empty array when nothing falls in range", () => {
    const dividends = [paidRecord(9)];
    expect(selectDividendHistory(dividends, "1y")).toEqual([]);
  });
});
