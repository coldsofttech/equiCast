import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { hasWarmedFxRates, warmFxRates } from "./fxWarmup.js";
import { getPrices } from "../api/market.js";

vi.mock("../api/market.js", () => ({ getPrices: vi.fn() }));

const PROFILE = {
  user_id: "auth0|abc",
  default_currency: "GBP",
  transaction_type: "AVERAGE",
  fx_warmup_currencies: ["GBP", "USD", "EUR"],
};

beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(getPrices).mockResolvedValue({ ticker: "GBPUSD", daily: [], weekly: [], monthly: [] });
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("warmFxRates", () => {
  it("fetches one pair's full history per configured currency, skipping the default currency itself", () => {
    const api = vi.fn();

    warmFxRates(api, PROFILE);

    expect(getPrices).toHaveBeenCalledTimes(2);
    const pairs = vi.mocked(getPrices).mock.calls.map(([, assetClass, symbol]) => [assetClass, symbol]);
    expect(pairs).toEqual(
      expect.arrayContaining([
        ["fx", "GBPUSD"],
        ["fx", "GBPEUR"],
      ])
    );
  });

  it("does nothing when profile is null", () => {
    const api = vi.fn();

    warmFxRates(api, null);

    expect(getPrices).not.toHaveBeenCalled();
  });

  it("only fires once per session, even across multiple calls", () => {
    const api = vi.fn();

    warmFxRates(api, PROFILE);
    warmFxRates(api, PROFILE);

    expect(getPrices).toHaveBeenCalledTimes(2);
  });

  it("never throws when a lookup rejects", async () => {
    vi.mocked(getPrices).mockRejectedValue(new Error("no data"));
    const api = vi.fn();

    expect(() => warmFxRates(api, PROFILE)).not.toThrow();
  });

  it("resolves once every lookup has settled, including a rejected one", async () => {
    vi.mocked(getPrices)
      .mockResolvedValueOnce({ ticker: "GBPUSD", daily: [], weekly: [], monthly: [] })
      .mockRejectedValueOnce(new Error("no data"));
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
