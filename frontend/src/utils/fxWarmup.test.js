import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { hasWarmedFxRates, warmFxRates } from "./fxWarmup.js";
import { getBulkPrices } from "../api/market.js";

vi.mock("../api/market.js", () => ({ getBulkPrices: vi.fn() }));

const PROFILE = {
  user_id: "auth0|abc",
  default_currency: "GBP",
  transaction_type: "AVERAGE",
  fx_warmup_currencies: ["GBP", "USD", "EUR"],
};

beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(getBulkPrices).mockResolvedValue([
    { ticker: "GBPUSD", daily: [], weekly: [], monthly: [] },
    { ticker: "GBPEUR", daily: [], weekly: [], monthly: [] },
  ]);
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("warmFxRates", () => {
  it("fetches one pair's full history per configured currency, skipping the default currency itself, in one bulk call", () => {
    const api = vi.fn();

    warmFxRates(api, PROFILE);

    expect(getBulkPrices).toHaveBeenCalledTimes(1);
    const [, items] = vi.mocked(getBulkPrices).mock.calls[0];
    expect(items).toEqual(
      expect.arrayContaining([
        { assetClass: "fx", symbol: "GBPUSD" },
        { assetClass: "fx", symbol: "GBPEUR" },
      ])
    );
  });

  it("does nothing when profile is null", () => {
    const api = vi.fn();

    warmFxRates(api, null);

    expect(getBulkPrices).not.toHaveBeenCalled();
  });

  it("only fires once per session, even across multiple calls", () => {
    const api = vi.fn();

    warmFxRates(api, PROFILE);
    warmFxRates(api, PROFILE);

    expect(getBulkPrices).toHaveBeenCalledTimes(1);
  });

  it("never throws when the bulk lookup rejects", async () => {
    vi.mocked(getBulkPrices).mockRejectedValue(new Error("no data"));
    const api = vi.fn();

    expect(() => warmFxRates(api, PROFILE)).not.toThrow();
  });

  it("resolves once the bulk lookup has settled, even when it rejects", async () => {
    vi.mocked(getBulkPrices).mockRejectedValueOnce(new Error("no data"));
    const api = vi.fn();

    await expect(warmFxRates(api, PROFILE)).resolves.toBeUndefined();
  });
});

describe("hasWarmedFxRates", () => {
  it("is false before warmFxRates has ever run", () => {
    expect(hasWarmedFxRates()).toBe(false);
  });

  it("is true once warmFxRates has run for a real profile", () => {
    warmFxRates(vi.fn(), PROFILE);

    expect(hasWarmedFxRates()).toBe(true);
  });

  it("stays false when warmFxRates short-circuits on a null profile", () => {
    warmFxRates(vi.fn(), null);

    expect(hasWarmedFxRates()).toBe(false);
  });
});
