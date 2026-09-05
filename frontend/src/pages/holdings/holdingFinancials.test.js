import { describe, expect, it, vi } from "vitest";
import {
  buildPlaceholderMetrics,
  deriveAverageModeFinancials,
  deriveInstanceFinancials,
  deriveTransactionModeFinancials,
  extractPriceWindow,
  formatPrice,
  resolveFxRate,
  rollupInstances,
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

describe("deriveAverageModeFinancials", () => {
  it("reads shares/avg price straight off the single AVERAGE record", () => {
    const result = deriveAverageModeFinancials([
      { no_of_shares: 10, average_price: 150 },
    ]);
    expect(result).toEqual({ shares: 10, avgPriceNative: 150, invested: 1500 });
  });

  it("returns zeros/null with no record yet", () => {
    expect(deriveAverageModeFinancials([])).toEqual({
      shares: 0,
      avgPriceNative: null,
      invested: 0,
    });
  });
});

describe("deriveTransactionModeFinancials", () => {
  it("computes weighted-average cost across multiple buys", () => {
    const result = deriveTransactionModeFinancials([
      { type: "BUY", no_of_shares: 10, price: 100, date: "2026-01-01" },
      { type: "BUY", no_of_shares: 10, price: 200, date: "2026-02-01" },
    ]);
    expect(result.shares).toBe(20);
    expect(result.avgPriceNative).toBeCloseTo(150);
    expect(result.invested).toBeCloseTo(3000);
  });

  it("keeps the average cost of remaining shares unchanged after a partial sell", () => {
    const result = deriveTransactionModeFinancials([
      { type: "BUY", no_of_shares: 10, price: 100, date: "2026-01-01" },
      { type: "SELL", no_of_shares: 4, price: 999, date: "2026-03-01" },
    ]);
    expect(result.shares).toBe(6);
    expect(result.avgPriceNative).toBeCloseTo(100);
    expect(result.invested).toBeCloseTo(600);
  });

  it("sorts out-of-order records by date before processing", () => {
    const result = deriveTransactionModeFinancials([
      { type: "SELL", no_of_shares: 4, price: 999, date: "2026-03-01" },
      { type: "BUY", no_of_shares: 10, price: 100, date: "2026-01-01" },
    ]);
    expect(result.shares).toBe(6);
    expect(result.avgPriceNative).toBeCloseTo(100);
  });

  it("returns a null avg price once every share has been sold", () => {
    const result = deriveTransactionModeFinancials([
      { type: "BUY", no_of_shares: 10, price: 100, date: "2026-01-01" },
      { type: "SELL", no_of_shares: 10, price: 200, date: "2026-02-01" },
    ]);
    expect(result).toEqual({ shares: 0, avgPriceNative: null, invested: 0 });
  });
});

describe("deriveInstanceFinancials", () => {
  it("dispatches to the AVERAGE derivation", () => {
    const result = deriveInstanceFinancials(
      [{ no_of_shares: 5, average_price: 20 }],
      "AVERAGE"
    );
    expect(result.invested).toBe(100);
  });

  it("dispatches to the TRANSACTION derivation", () => {
    const result = deriveInstanceFinancials(
      [{ type: "BUY", no_of_shares: 5, price: 20, date: "2026-01-01" }],
      "TRANSACTION"
    );
    expect(result.invested).toBe(100);
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

describe("extractPriceWindow", () => {
  const results = [
    { high: 10, low: 8, close: 9 },
    { high: 12, low: 9, close: 11 },
    { high: 11, low: 10, close: 10.5 },
    { high: 14, low: 10, close: 13 },
  ];

  it("takes the trailing N records and finds their high/low", () => {
    const window = extractPriceWindow(results, 2);
    expect(window).toEqual({ high: 14, low: 10, closes: [10.5, 13], sufficient: true });
  });

  it("flags insufficient data when fewer than 3 days are available for a >=3-day window", () => {
    const window = extractPriceWindow(results.slice(0, 2), 7);
    expect(window.sufficient).toBe(false);
  });

  it("handles no published prices at all", () => {
    expect(extractPriceWindow(null, 7)).toEqual({
      high: null,
      low: null,
      closes: [],
      sufficient: false,
    });
  });
});

describe("buildPlaceholderMetrics", () => {
  it("is deterministic per ticker", () => {
    expect(buildPlaceholderMetrics("AAPL")).toEqual(buildPlaceholderMetrics("AAPL"));
  });

  it("differs between tickers", () => {
    expect(buildPlaceholderMetrics("AAPL")).not.toEqual(buildPlaceholderMetrics("MSFT"));
  });
});
