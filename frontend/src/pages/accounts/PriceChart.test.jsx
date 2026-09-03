import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PriceChart from "./PriceChart.jsx";

const PIES = [
  { id: "p-1", name: "Growth" },
  { id: "p-2", name: "Income" },
];

describe("PriceChart", () => {
  it("renders with Candles and 1Y active by default", () => {
    render(<PriceChart pies={PIES} seedKey="account:test" />);

    expect(screen.getByRole("button", { name: "Candles" })).toHaveClass("is-active");
    expect(screen.getByRole("button", { name: "1Y" })).toHaveClass("is-active");
    expect(screen.getByText("This account")).toBeInTheDocument();
  });

  it("switches chart type on click", () => {
    render(<PriceChart pies={PIES} seedKey="account:test" />);

    fireEvent.click(screen.getByRole("button", { name: "Area" }));

    expect(screen.getByRole("button", { name: "Area" })).toHaveClass("is-active");
    expect(screen.getByRole("button", { name: "Candles" })).not.toHaveClass("is-active");
  });

  it.each(["1D", "5D", "1M", "6M", "YTD", "2Y", "3Y", "5Y", "10Y", "MAX"])(
    "switches to the %s range without crashing",
    (label) => {
      render(<PriceChart pies={PIES} seedKey="account:test" />);

      fireEvent.click(screen.getByRole("button", { name: label }));

      expect(screen.getByRole("button", { name: label })).toHaveClass("is-active");
    }
  );

  it("lists this account's other portfolios and benchmarks in the compare picker", () => {
    render(<PriceChart pies={PIES} seedKey="account:test" />);

    const select = screen.getByLabelText("Compare against");
    const optionLabels = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);

    expect(optionLabels).toEqual(
      expect.arrayContaining(["Growth", "Income", "S&P 500", "NASDAQ 100", "FTSE 100"])
    );
  });

  it("shows a compare legend entry once a benchmark is selected", () => {
    render(<PriceChart pies={PIES} seedKey="account:test" />);

    fireEvent.change(screen.getByLabelText("Compare against"), {
      target: { value: "benchmark:sp500" },
    });

    // "S&P 500" now appears twice: once as the <option>, once in the legend.
    expect(screen.getAllByText("S&P 500")).toHaveLength(2);
  });

  it("works with no portfolios to compare against", () => {
    render(<PriceChart pies={[]} seedKey="account:test" />);

    const select = screen.getByLabelText("Compare against");
    const optionLabels = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);

    expect(optionLabels).toEqual(
      expect.arrayContaining(["S&P 500", "NASDAQ 100", "FTSE 100"])
    );
    expect(select.querySelectorAll("optgroup")).toHaveLength(1);
  });

  it("lists other holdings in the compare picker when passed", () => {
    const holdings = [
      { id: "h-1", name: "MSFT" },
      { id: "h-2", name: "GOOGL" },
    ];
    render(<PriceChart holdings={holdings} seedKey="holding:AAPL" subjectLabel="This holding" />);

    const select = screen.getByLabelText("Compare against");
    const optionLabels = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);

    expect(optionLabels).toEqual(expect.arrayContaining(["MSFT", "GOOGL"]));
    expect(
      Array.from(select.querySelectorAll("optgroup")).map((g) => g.label)
    ).toContain("Other holdings");
  });

  it("shows a compare legend entry once another holding is selected", () => {
    const holdings = [{ id: "h-1", name: "MSFT" }];
    render(<PriceChart holdings={holdings} seedKey="holding:AAPL" subjectLabel="This holding" />);

    fireEvent.change(screen.getByLabelText("Compare against"), {
      target: { value: "holding:h-1" },
    });

    expect(screen.getAllByText("MSFT")).toHaveLength(2);
  });
});
