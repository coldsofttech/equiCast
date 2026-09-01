import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SearchFilters from "./SearchFilters.jsx";

describe("SearchFilters", () => {
  it("starts with the currently-applied type selected", () => {
    render(<SearchFilters type="etf" onApply={vi.fn()} />);

    expect(screen.getByLabelText("ETFs")).toBeChecked();
    expect(screen.getByLabelText("All types")).not.toBeChecked();
  });

  it("calls onApply with the selected type only after clicking Search", () => {
    const onApply = vi.fn();
    render(<SearchFilters type="" onApply={onApply} />);

    fireEvent.click(screen.getByLabelText("Stocks"));
    expect(onApply).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(onApply).toHaveBeenCalledWith("stock");
  });

  it("disables Region/Exchange/Market cap as coming-soon placeholders", () => {
    render(<SearchFilters type="" onApply={vi.fn()} />);

    expect(screen.getByText("Region").closest("fieldset")).toBeDisabled();
    expect(screen.getByText("Exchange").closest("fieldset")).toBeDisabled();
    expect(screen.getByText("Market cap").closest("fieldset")).toBeDisabled();
    expect(screen.getAllByText("Coming soon")).toHaveLength(3);
  });

  it("resets the draft selection when the applied type prop changes", () => {
    const { rerender } = render(<SearchFilters type="" onApply={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("FX"));
    expect(screen.getByLabelText("FX")).toBeChecked();

    rerender(<SearchFilters type="stock" onApply={vi.fn()} />);

    expect(screen.getByLabelText("Stocks")).toBeChecked();
    expect(screen.getByLabelText("FX")).not.toBeChecked();
  });
});
