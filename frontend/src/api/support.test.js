import { describe, expect, it, vi } from "vitest";
import { submitSupportRequest } from "./support.js";

describe("support api", () => {
  it("posts a support request to /support/", async () => {
    const api = vi.fn().mockResolvedValue({ detail: "Thanks — we've received this." });

    const result = await submitSupportRequest(api, {
      category: "ticker-request",
      description: "Please add NVDA.",
      ticker: "NVDA",
    });

    expect(api).toHaveBeenCalledWith("/support/", {
      method: "POST",
      body: { category: "ticker-request", description: "Please add NVDA.", ticker: "NVDA" },
    });
    expect(result).toEqual({ detail: "Thanks — we've received this." });
  });
});
