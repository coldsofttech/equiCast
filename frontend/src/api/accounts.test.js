import { describe, expect, it, vi } from "vitest";
import { createAccount, deleteAccount, getAccount, listAccounts, updateAccount } from "./accounts.js";

describe("accounts api", () => {
  it("lists accounts from /accounts/", async () => {
    const api = vi.fn().mockResolvedValue([{ id: "a-1" }]);

    const result = await listAccounts(api);

    expect(api).toHaveBeenCalledWith("/accounts/");
    expect(result).toEqual([{ id: "a-1" }]);
  });

  it("gets one account by id", async () => {
    const api = vi.fn().mockResolvedValue({ id: "a-1" });

    await getAccount(api, "a-1");

    expect(api).toHaveBeenCalledWith("/accounts/a-1/");
  });

  it("posts a new account", async () => {
    const api = vi.fn().mockResolvedValue({ id: "a-1" });
    const data = {
      name: "ISA",
      description: "Stocks and shares ISA",
      account_type: "ISA",
      currency: "GBP",
      transaction_type: "AVERAGE",
    };

    await createAccount(api, data);

    expect(api).toHaveBeenCalledWith("/accounts/", { method: "POST", body: data });
  });

  it("patches only the given fields", async () => {
    const api = vi.fn().mockResolvedValue({ id: "a-1" });

    await updateAccount(api, "a-1", { name: "Renamed" });

    expect(api).toHaveBeenCalledWith("/accounts/a-1/", {
      method: "PATCH",
      body: { name: "Renamed" },
    });
  });

  it("deletes without a force query param by default", async () => {
    const api = vi.fn().mockResolvedValue(null);

    await deleteAccount(api, "a-1");

    expect(api).toHaveBeenCalledWith("/accounts/a-1/", { method: "DELETE" });
  });

  it("appends ?force=true when force is requested", async () => {
    const api = vi.fn().mockResolvedValue(null);

    await deleteAccount(api, "a-1", { force: true });

    expect(api).toHaveBeenCalledWith("/accounts/a-1/?force=true", { method: "DELETE" });
  });
});
