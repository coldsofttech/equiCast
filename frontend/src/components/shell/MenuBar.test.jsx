import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MenuBar from "./MenuBar.jsx";

const ITEMS = [
  { id: "portfolio", label: "Portfolio" },
  { id: "watchlists", label: "Watchlists" },
  { id: "search", label: "Search" },
];

describe("MenuBar", () => {
  it("renders every item, with the first active by default", () => {
    render(<MenuBar items={ITEMS} />);

    expect(screen.getByRole("button", { name: "Portfolio" })).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(screen.getByRole("button", { name: "Watchlists" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("respects an explicit defaultActiveId", () => {
    render(<MenuBar items={ITEMS} defaultActiveId="search" />);

    expect(screen.getByRole("button", { name: "Search" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Portfolio" })).not.toHaveAttribute("aria-current");
  });

  it("marks a clicked item active instead", () => {
    render(<MenuBar items={ITEMS} />);

    fireEvent.click(screen.getByRole("button", { name: "Watchlists" }));

    expect(screen.getByRole("button", { name: "Watchlists" })).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(screen.getByRole("button", { name: "Portfolio" })).not.toHaveAttribute("aria-current");
  });

  it("toggles the mobile menu open/closed", () => {
    render(<MenuBar items={ITEMS} />);
    const toggle = screen.getByRole("button", { name: /menu/i });

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
