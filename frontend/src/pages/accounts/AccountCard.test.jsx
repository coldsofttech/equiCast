import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AccountCard from "./AccountCard.jsx";

const ACCOUNT = {
  id: "a-1",
  name: "Stocks & Shares ISA",
  description: "Long-term holdings",
  account_type: "ISA",
  currency: "GBP",
  transaction_type: "AVERAGE",
  pies: [{ id: "p-1" }, { id: "p-2" }],
};

describe("AccountCard", () => {
  it("renders the account's summary", () => {
    render(<AccountCard account={ACCOUNT} onClick={vi.fn()} />);

    expect(screen.getByText("Stocks & Shares ISA")).toBeInTheDocument();
    expect(screen.getByText("ISA")).toBeInTheDocument();
    expect(screen.getByText("Long-term holdings")).toBeInTheDocument();
    expect(screen.getByText("GBP")).toBeInTheDocument();
    expect(screen.getByText("Average cost")).toBeInTheDocument();
    expect(screen.getByText("2 pies")).toBeInTheDocument();
  });

  it("shows Per-transaction for TRANSACTION accounts", () => {
    render(<AccountCard account={{ ...ACCOUNT, transaction_type: "TRANSACTION" }} onClick={vi.fn()} />);

    expect(screen.getByText("Per-transaction")).toBeInTheDocument();
  });

  it("calls onClick when clicked or activated via keyboard", () => {
    const onClick = vi.fn();
    render(<AccountCard account={ACCOUNT} onClick={onClick} />);

    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(screen.getByRole("button"), { key: "Enter" });
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it("defaults pies count to 0 when absent", () => {
    const { pies, ...withoutPies } = ACCOUNT;
    void pies;
    render(<AccountCard account={withoutPies} onClick={vi.fn()} />);

    expect(screen.getByText("0 pies")).toBeInTheDocument();
  });
});
