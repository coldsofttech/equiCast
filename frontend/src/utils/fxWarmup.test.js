import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { warmFxRates } from "./fxWarmup.js";
import { getFxRateOnDate } from "../api/market.js";

vi.mock("../api/market.js", () => ({ getFxRateOnDate: vi.fn() }));

const PROFILE = {
  user_id: "auth0|abc",
  default_currency: "GBP",
  transaction_type: "AVERAGE",
  fx_warmup_currencies: ["GBP", "USD", "EUR"],
};

beforeEach(() => {
  sessionStorage.clear();
  vi.mocked(getFxRateOnDate).mockResolvedValue({ rate: 1.2 });
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("warmFxRates", () => {
  it("fetches one rate per configured currency, skipping the default currency itself", () => {
    const api = vi.fn();

    warmFxRates(api, PROFILE);

    expect(getFxRateOnDate).toHaveBeenCalledTimes(2);
    const pairs = vi.mocked(getFxRateOnDate).mock.calls.map(([, from, to]) => [from, to]);
    expect(pairs).toEqual(
      expect.arrayContaining([
        ["GBP", "USD"],
        ["GBP", "EUR"],
      ])
    );
  });

  it("does nothing when profile is null", () => {
    const api = vi.fn();

    warmFxRates(api, null);

    expect(getFxRateOnDate).not.toHaveBeenCalled();
  });

  it("only fires once per session, even across multiple calls", () => {
    const api = vi.fn();

    warmFxRates(api, PROFILE);
    warmFxRates(api, PROFILE);

    expect(getFxRateOnDate).toHaveBeenCalledTimes(2);
  });

  it("never throws when a lookup rejects", async () => {
    vi.mocked(getFxRateOnDate).mockRejectedValue(new Error("no data"));
    const api = vi.fn();

    expect(() => warmFxRates(api, PROFILE)).not.toThrow();
  });
});
