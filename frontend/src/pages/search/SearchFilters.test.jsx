import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SearchFilters from "./SearchFilters.jsx";

const DEFAULT_APPLY = {
  q: "",
  type: "",
  region: "",
  exchange: "",
  sector: "",
  industry: "",
  minMarketCap: undefined,
  maxMarketCap: undefined,
};

describe("SearchFilters", () => {
  it("starts with the currently-applied type selected", () => {
    render(<SearchFilters type="etf" onApply={vi.fn()} />);

    expect(screen.getByLabelText("ETFs")).toBeChecked();
    expect(screen.getByLabelText("All types")).not.toBeChecked();
  });

  it("calls onApply with every filter's default value, only after clicking Search", () => {
    const onApply = vi.fn();
    render(<SearchFilters type="" onApply={onApply} />);

    fireEvent.click(screen.getByLabelText("Stocks"));
    expect(onApply).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(onApply).toHaveBeenCalledWith({ ...DEFAULT_APPLY, type: "stock" });
  });

  it("calls onApply with the slider's market cap bounds after moving it", () => {
    const onApply = vi.fn();
    render(<SearchFilters type="" onApply={onApply} />);

    fireEvent.change(screen.getByLabelText("Minimum"), { target: { value: "4" } });
    fireEvent.change(screen.getByLabelText("Maximum"), { target: { value: "8" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(onApply).toHaveBeenCalledWith({
      ...DEFAULT_APPLY,
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

  it("calls onApply with the selected region and exchange after clicking Search", () => {
    const onApply = vi.fn();
    render(<SearchFilters type="" onApply={onApply} />);

    fireEvent.change(screen.getByLabelText("Region"), { target: { value: "gb" } });
    fireEvent.change(screen.getByLabelText("Exchange"), { target: { value: "LSE" } });
    expect(onApply).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(onApply).toHaveBeenCalledWith({ ...DEFAULT_APPLY, region: "gb", exchange: "LSE" });
  });

  it("starts with the currently-applied region/exchange selected", () => {
    render(<SearchFilters type="" region="gb" exchange="LSE" onApply={vi.fn()} />);

    expect(screen.getByLabelText("Region")).toHaveValue("gb");
    expect(screen.getByLabelText("Exchange")).toHaveValue("LSE");
  });

  it("resets the draft region/exchange when the applied props change", () => {
    const { rerender } = render(<SearchFilters type="" onApply={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Region"), { target: { value: "gb" } });
    expect(screen.getByLabelText("Region")).toHaveValue("gb");

    rerender(<SearchFilters type="" region="us" onApply={vi.fn()} />);

    expect(screen.getByLabelText("Region")).toHaveValue("us");
  });

  it("calls onApply with the selected sector and industry after clicking Search", () => {
    const onApply = vi.fn();
    render(<SearchFilters type="" onApply={onApply} />);

    fireEvent.change(screen.getByLabelText("Sector"), { target: { value: "Technology" } });
    fireEvent.change(screen.getByLabelText("Industry"), { target: { value: "Semiconductors" } });
    expect(onApply).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(onApply).toHaveBeenCalledWith({
      ...DEFAULT_APPLY,
      sector: "Technology",
      industry: "Semiconductors",
    });
  });

  it("starts with the currently-applied sector/industry selected", () => {
    render(
      <SearchFilters type="" sector="Technology" industry="Semiconductors" onApply={vi.fn()} />
    );

    expect(screen.getByLabelText("Sector")).toHaveValue("Technology");
    expect(screen.getByLabelText("Industry")).toHaveValue("Semiconductors");
  });

  it("resets the draft sector/industry when the applied props change", () => {
    const { rerender } = render(<SearchFilters type="" onApply={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Sector"), { target: { value: "Technology" } });
    expect(screen.getByLabelText("Sector")).toHaveValue("Technology");

    rerender(<SearchFilters type="" sector="Consumer Cyclical" onApply={vi.fn()} />);

    expect(screen.getByLabelText("Sector")).toHaveValue("Consumer Cyclical");
  });

  it("resets the draft selection when the applied type prop changes", () => {
    const { rerender } = render(<SearchFilters type="" onApply={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("FX"));
    expect(screen.getByLabelText("FX")).toBeChecked();

    rerender(<SearchFilters type="stock" onApply={vi.fn()} />);

    expect(screen.getByLabelText("Stocks")).toBeChecked();
    expect(screen.getByLabelText("FX")).not.toBeChecked();
  });

  it("starts with Clear disabled when every filter is already at its default", () => {
    render(<SearchFilters type="" onApply={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Clear filters" })).toBeDisabled();
  });

  it("enables Clear once a draft filter changes", () => {
    render(<SearchFilters type="" onApply={vi.fn()} />);

    fireEvent.click(screen.getByLabelText("Stocks"));

    expect(screen.getByRole("button", { name: "Clear filters" })).not.toBeDisabled();
  });

  it("clicking Clear resets every draft, Keyword included, and applies immediately, without a separate Search click", () => {
    const onApply = vi.fn();
    render(<SearchFilters query="aapl" type="" onApply={onApply} />);

    fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "nvda" } });
    fireEvent.click(screen.getByLabelText("Stocks"));
    fireEvent.change(screen.getByLabelText("Region"), { target: { value: "gb" } });
    fireEvent.change(screen.getByLabelText("Exchange"), { target: { value: "LSE" } });
    fireEvent.change(screen.getByLabelText("Sector"), { target: { value: "Technology" } });
    fireEvent.change(screen.getByLabelText("Industry"), { target: { value: "Semiconductors" } });
    fireEvent.change(screen.getByLabelText("Minimum"), { target: { value: "4" } });

    fireEvent.click(screen.getByRole("button", { name: "Clear filters" }));

    expect(onApply).toHaveBeenCalledWith(DEFAULT_APPLY);
    expect(screen.getByLabelText("Keyword")).toHaveValue("");
    expect(screen.getByLabelText("All types")).toBeChecked();
    expect(screen.getByLabelText("Region")).toHaveValue("");
    expect(screen.getByLabelText("Exchange")).toHaveValue("");
    expect(screen.getByLabelText("Sector")).toHaveValue("");
    expect(screen.getByLabelText("Industry")).toHaveValue("");
    expect(screen.getByLabelText("Minimum")).toHaveValue("0");
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeDisabled();
  });

  it("Clear reflects applied filters, not just draft ones, when nothing has been changed yet", () => {
    render(<SearchFilters type="stock" onApply={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Clear filters" })).not.toBeDisabled();
  });

  it("starts the Keyword field empty when no query is applied", () => {
    render(<SearchFilters type="" onApply={vi.fn()} />);

    expect(screen.getByLabelText("Keyword")).toHaveValue("");
  });

  it("auto-populates the Keyword field from an applied query, e.g. from the topbar search", () => {
    render(<SearchFilters query="aapl" type="" onApply={vi.fn()} />);

    expect(screen.getByLabelText("Keyword")).toHaveValue("aapl");
  });

  it("resets the draft Keyword when the applied query prop changes", () => {
    const { rerender } = render(<SearchFilters query="aapl" type="" onApply={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "nvda" } });
    expect(screen.getByLabelText("Keyword")).toHaveValue("nvda");

    rerender(<SearchFilters query="msft" type="" onApply={vi.fn()} />);

    expect(screen.getByLabelText("Keyword")).toHaveValue("msft");
  });

  it("includes the trimmed Keyword value in onApply after clicking Search", () => {
    const onApply = vi.fn();
    render(<SearchFilters query="aapl" type="" onApply={onApply} />);

    fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "  nvda  " } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(onApply).toHaveBeenCalledWith({ ...DEFAULT_APPLY, q: "nvda" });
  });

  it("applies the Keyword field on pressing Enter, without a separate Search click", () => {
    const onApply = vi.fn();
    render(<SearchFilters query="aapl" type="" onApply={onApply} />);

    fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "nvda" } });
    fireEvent.keyDown(screen.getByLabelText("Keyword"), { key: "Enter" });

    expect(onApply).toHaveBeenCalledWith({ ...DEFAULT_APPLY, q: "nvda" });
  });

  it("enables Clear once the Keyword field changes, even with every other filter at its default", () => {
    render(<SearchFilters type="" onApply={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Keyword"), { target: { value: "aapl" } });

    expect(screen.getByRole("button", { name: "Clear filters" })).not.toBeDisabled();
  });
});
