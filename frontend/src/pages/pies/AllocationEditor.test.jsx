import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import AllocationEditor from "./AllocationEditor.jsx";

const HOLDINGS = [
  { id: "h-1", ticker: "AAPL", asset_class: "stock", allocation_pct: "60" },
  { id: "h-2", ticker: "VUSA", asset_class: "etf", allocation_pct: "40" },
];

describe("AllocationEditor", () => {
  it("shows the current total and disables save with no edits", () => {
    render(<AllocationEditor holdings={HOLDINGS} onSave={vi.fn()} />);

    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("reallocates an existing holding and only sends what changed", () => {
    const onSave = vi.fn();
    render(<AllocationEditor holdings={HOLDINGS} onSave={onSave} />);

    fireEvent.change(screen.getAllByLabelText("Allocation percent")[0], {
      target: { value: "70" },
    });
    fireEvent.change(screen.getAllByLabelText("Allocation percent")[1], {
      target: { value: "30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(onSave).toHaveBeenCalledWith({
      add: [],
      remove: [],
      reallocate: [
        { id: "h-1", allocation_pct: "70" },
        { id: "h-2", allocation_pct: "30" },
      ],
    });
  });

  it("adds a new holding, uppercasing its ticker", () => {
    const onSave = vi.fn();
    render(<AllocationEditor holdings={[HOLDINGS[0]]} onSave={onSave} />);

    fireEvent.change(screen.getAllByLabelText("Allocation percent")[0], {
      target: { value: "50" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add holding" }));
    fireEvent.change(screen.getAllByLabelText("Ticker")[1], { target: { value: "vwrl" } });
    fireEvent.change(screen.getAllByLabelText("Asset class")[1], { target: { value: "etf" } });
    fireEvent.change(screen.getAllByLabelText("Allocation percent")[1], {
      target: { value: "50" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(onSave).toHaveBeenCalledWith({
      add: [{ ticker: "VWRL", asset_class: "etf", allocation_pct: "50" }],
      remove: [],
      reallocate: [{ id: "h-1", allocation_pct: "50" }],
    });
  });

  it("removes an existing holding", () => {
    const onSave = vi.fn();
    render(<AllocationEditor holdings={[HOLDINGS[0]]} onSave={onSave} />);

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    expect(screen.queryByLabelText("Ticker")).not.toBeInTheDocument();
    expect(screen.getByText("No holdings yet — add one below.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(onSave).toHaveBeenCalledWith({ add: [], remove: ["h-1"], reallocate: [] });
  });

  it("keeps save disabled while the total isn't 100%", () => {
    render(<AllocationEditor holdings={HOLDINGS} onSave={vi.fn()} />);

    fireEvent.change(screen.getAllByLabelText("Allocation percent")[0], {
      target: { value: "70" },
    });

    expect(screen.getByText("110%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });

  it("surfaces a save error passed in via props", () => {
    render(<AllocationEditor holdings={HOLDINGS} onSave={vi.fn()} error="Pie holdings must sum to exactly 100%." />);

    expect(screen.getByRole("alert")).toHaveTextContent("Pie holdings must sum to exactly 100%.");
  });
});
