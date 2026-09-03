import { describe, expect, it, vi } from "vitest";
import {
  createTransaction,
  deleteTransaction,
  getTransaction,
  listTransactions,
  updateTransaction,
} from "./transactions.js";

describe("transactions api", () => {
  it("lists every transaction for one holding", async () => {
    const api = vi.fn().mockResolvedValue([]);

    await listTransactions(api, { holdingId: "h-1" });

    expect(api).toHaveBeenCalledWith("/transactions/?holding_id=h-1");
  });

  it("lists every transaction for the caller when no holding is given", async () => {
    const api = vi.fn().mockResolvedValue([]);

    await listTransactions(api);

    expect(api).toHaveBeenCalledWith("/transactions/");
  });

  it("gets one transaction by holding and transaction id", async () => {
    const api = vi.fn().mockResolvedValue({ id: "t-1" });

    await getTransaction(api, "h-1", "t-1");

    expect(api).toHaveBeenCalledWith("/transactions/h-1/t-1/");
  });

  it("creates an AVERAGE-mode transaction", async () => {
    const api = vi.fn().mockResolvedValue({ id: "t-1" });
    const data = { holding_id: "h-1", no_of_shares: 10, average_price: 150 };

    await createTransaction(api, data);

    expect(api).toHaveBeenCalledWith("/transactions/", { method: "POST", body: data });
  });

  it("updates an AVERAGE-mode transaction", async () => {
    const api = vi.fn().mockResolvedValue({ id: "t-1" });

    await updateTransaction(api, "h-1", "t-1", { no_of_shares: 12 });

    expect(api).toHaveBeenCalledWith("/transactions/h-1/t-1/", {
      method: "PATCH",
      body: { no_of_shares: 12 },
    });
  });

  it("deletes a transaction", async () => {
    const api = vi.fn().mockResolvedValue(null);

    await deleteTransaction(api, "h-1", "t-1");

    expect(api).toHaveBeenCalledWith("/transactions/h-1/t-1/", { method: "DELETE" });
  });
});
