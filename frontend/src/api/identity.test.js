import { describe, expect, it, vi } from "vitest";
import {
  getMe,
  updateDefaultCurrency,
  updateFxWarmupCurrencies,
  updateIncomeTaxBand,
  updateTaxResidency,
} from "./identity.js";

describe("identity api", () => {
  it("gets the caller's profile from /identity/me/", async () => {
    const api = vi.fn().mockResolvedValue({ user_id: "auth0|abc", default_currency: "GBP" });

    const result = await getMe(api);

    expect(api).toHaveBeenCalledWith("/identity/me/");
    expect(result).toEqual({ user_id: "auth0|abc", default_currency: "GBP" });
  });

  it("patches default_currency", async () => {
    const api = vi.fn().mockResolvedValue({ user_id: "auth0|abc", default_currency: "EUR" });

    await updateDefaultCurrency(api, "EUR");

    expect(api).toHaveBeenCalledWith("/identity/me/", {
      method: "PATCH",
      body: { default_currency: "EUR" },
    });
  });

  it("patches fx_warmup_currencies", async () => {
    const api = vi.fn().mockResolvedValue({
      user_id: "auth0|abc",
      fx_warmup_currencies: ["GBP", "INR"],
    });

    await updateFxWarmupCurrencies(api, ["GBP", "INR"]);

    expect(api).toHaveBeenCalledWith("/identity/me/", {
      method: "PATCH",
      body: { fx_warmup_currencies: ["GBP", "INR"] },
    });
  });

  it("patches tax_residency", async () => {
    const api = vi.fn().mockResolvedValue({ user_id: "auth0|abc", tax_residency: "UK" });

    await updateTaxResidency(api, "UK");

    expect(api).toHaveBeenCalledWith("/identity/me/", {
      method: "PATCH",
      body: { tax_residency: "UK" },
    });
  });

  it("patches income_tax_band", async () => {
    const api = vi.fn().mockResolvedValue({ user_id: "auth0|abc", income_tax_band: "HIGHER" });

    await updateIncomeTaxBand(api, "HIGHER");

    expect(api).toHaveBeenCalledWith("/identity/me/", {
      method: "PATCH",
      body: { income_tax_band: "HIGHER" },
    });
  });
});
