import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AccountPriceChart from "./AccountPriceChart.jsx";

const PIES = [
  { id: "p-1", name: "Growth" },
  { id: "p-2", name: "Income" },
];

describe("AccountPriceChart", () => {
  it("renders with Candles and 1Y active by default", () => {
    render(<AccountPriceChart pies={PIES} />);

    expect(screen.getByRole("button", { name: "Candles" })).toHaveClass("is-active");
    expect(screen.getByRole("button", { name: "1Y" })).toHaveClass("is-active");
    expect(screen.getByText("This account")).toBeInTheDocument();
  });

  it("switches chart type on click", () => {
    render(<AccountPriceChart pies={PIES} />);

    fireEvent.click(screen.getByRole("button", { name: "Area" }));

    expect(screen.getByRole("button", { name: "Area" })).toHaveClass("is-active");
    expect(screen.getByRole("button", { name: "Candles" })).not.toHaveClass("is-active");
  });

  it.each(["1D", "5D", "1M", "6M", "YTD", "2Y", "3Y", "5Y", "10Y", "MAX"])(
    "switches to the %s range without crashing",
    (label) => {
      render(<AccountPriceChart pies={PIES} />);

      fireEvent.click(screen.getByRole("button", { name: label }));

      expect(screen.getByRole("button", { name: label })).toHaveClass("is-active");
    }
  );

  it("lists this account's other portfolios and benchmarks in the compare picker", () => {
    render(<AccountPriceChart pies={PIES} />);

    const select = screen.getByLabelText("Compare against");
    const optionLabels = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);

    expect(optionLabels).toEqual(
      expect.arrayContaining(["Growth", "Income", "S&P 500", "NASDAQ 100", "FTSE 100"])
    );
  });

  it("shows a compare legend entry once a benchmark is selected", () => {
    render(<AccountPriceChart pies={PIES} />);

    fireEvent.change(screen.getByLabelText("Compare against"), {
      target: { value: "benchmark:sp500" },
    });

    // "S&P 500" now appears twice: once as the <option>, once in the legend.
    expect(screen.getAllByText("S&P 500")).toHaveLength(2);
  });

  it("works with no portfolios to compare against", () => {
    render(<AccountPriceChart pies={[]} />);

    const select = screen.getByLabelText("Compare against");
    const optionLabels = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);

    expect(optionLabels).toEqual(
      expect.arrayContaining(["S&P 500", "NASDAQ 100", "FTSE 100"])
    );
    expect(select.querySelectorAll("optgroup")).toHaveLength(1);
  });
});
