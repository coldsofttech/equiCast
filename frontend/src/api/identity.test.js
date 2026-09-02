import { describe, expect, it, vi } from "vitest";
import { getMe, updateDefaultCurrency } from "./identity.js";

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
});
