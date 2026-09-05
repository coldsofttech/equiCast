import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SearchFilters from "./SearchFilters.jsx";

describe("SearchFilters", () => {
  it("starts with the currently-applied type selected", () => {
    render(<SearchFilters type="etf" onApply={vi.fn()} />);

    expect(screen.getByLabelText("ETFs")).toBeChecked();
    expect(screen.getByLabelText("All types")).not.toBeChecked();
  });

  it("calls onApply with the selected type and no market cap bounds by default, only after clicking Search", () => {
    const onApply = vi.fn();
    render(<SearchFilters type="" onApply={onApply} />);

    fireEvent.click(screen.getByLabelText("Stocks"));
    expect(onApply).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(onApply).toHaveBeenCalledWith({
      type: "stock",
      minMarketCap: undefined,
      maxMarketCap: undefined,
    });
  });

  it("calls onApply with the slider's market cap bounds after moving it", () => {
    const onApply = vi.fn();
    render(<SearchFilters type="" onApply={onApply} />);

    fireEvent.change(screen.getByLabelText("Minimum"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Maximum"), { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(onApply).toHaveBeenCalledWith({
      type: "",
      minMarketCap: 1_000_000_000,
      maxMarketCap: 1_000_000_000_000,
    });
  });

  it("restores the slider from applied minMarketCap/maxMarketCap props", () => {
    render(
      <SearchFilters
        type=""
        minMarketCap={1_000_000_000}
        maxMarketCap={1_000_000_000_000}
        onApply={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Minimum")).toHaveValue("4");
    expect(screen.getByLabelText("Maximum")).toHaveValue("8");
  });

  it("disables Region/Exchange as coming-soon placeholders, but not Market cap", () => {
    render(<SearchFilters type="" onApply={vi.fn()} />);

    expect(screen.getByText("Region").closest("fieldset")).toBeDisabled();
    expect(screen.getByText("Exchange").closest("fieldset")).toBeDisabled();
    expect(screen.getByText("Market cap").closest("fieldset")).not.toBeDisabled();
    expect(screen.getAllByText("Coming soon")).toHaveLength(2);
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
