import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import WatchlistEntryCard from "./WatchlistEntryCard.jsx";

describe("WatchlistEntryCard", () => {
  it("renders a system entry's name, ticker, native price, and change", () => {
    const holding = {
      asset_class: "future",
      ticker: "GOLD",
      name: "Gold",
      currency: "USD",
      current_price: 2440.3,
      change_1w_pct: 1.2,
      change_1m_pct: -0.4,
    };

    render(<WatchlistEntryCard holding={holding} />);

    expect(screen.getByText("Gold")).toBeInTheDocument();
    expect(screen.getByText("GOLD")).toBeInTheDocument();
    expect(screen.getByText("$2,440.30")).toBeInTheDocument();
    expect(screen.getByText("+1.20%")).toBeInTheDocument();
    expect(screen.getByText("-0.40%")).toBeInTheDocument();
  });

  it("falls back to the ticker when name is missing", () => {
    render(<WatchlistEntryCard holding={{ ticker: "GC=F" }} />);

    expect(screen.getAllByText("GC=F")).toHaveLength(2); // name slot + ticker slot
  });

  it("prefers current_price_native over current_price for a real holding", () => {
    const holding = {
      ticker: "AAPL",
      name: "Apple Inc.",
      currency: "USD",
      current_price_native: 227.5,
      current_price: 180.0, // converted to some other default_currency
    };

    render(<WatchlistEntryCard holding={holding} />);

    expect(screen.getByText("$227.50")).toBeInTheDocument();
    expect(screen.queryByText("$180.00")).not.toBeInTheDocument();
  });

  it("shows a dash for price and change when unavailable", () => {
    render(<WatchlistEntryCard holding={{ ticker: "GOLD", name: "Gold" }} />);

    const dashes = screen.getAllByText("—");
    expect(dashes).toHaveLength(3); // price + 1W + 1M
  });

  it("shows a 1Y change stat only when change_1y_pct is present", () => {
    const { rerender } = render(
      <WatchlistEntryCard holding={{ ticker: "AAPL", change_1y_pct: 15.5 }} />
    );
    expect(screen.getByText("+15.50%")).toBeInTheDocument();

    rerender(<WatchlistEntryCard holding={{ ticker: "AAPL" }} />);
    expect(screen.queryByText(/15\.50%/)).not.toBeInTheDocument();
  });

  it("shows a remove button only when isRemovable, and wires onRemove", () => {
    const onRemove = vi.fn();
    const { rerender } = render(
      <WatchlistEntryCard holding={{ ticker: "AAPL" }} isRemovable onRemove={onRemove} />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove AAPL" }));
    expect(onRemove).toHaveBeenCalledTimes(1);

    rerender(<WatchlistEntryCard holding={{ ticker: "AAPL" }} />);
    expect(screen.queryByRole("button", { name: "Remove AAPL" })).not.toBeInTheDocument();
  });
});
