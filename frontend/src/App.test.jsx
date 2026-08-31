import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "./App.jsx";

beforeEach(() => {
  document.documentElement.setAttribute("data-theme", "light");
  localStorage.clear();
});

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
});

describe("App", () => {
  it("renders the equiCast wordmark", () => {
    render(<App />);
    // "Cast" is its own <b> element (a real text-node match); "equi" is a
    // sibling text node in the same <span>, not matchable as its own
    // element, so the full wordmark is asserted via the parent instead.
    const bold = screen.getByText("Cast");
    expect(bold.closest(".ec-logo-wordmark")).toHaveTextContent("equiCast");
  });

  it("renders the page title", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "App shell" })).toBeInTheDocument();
  });

  it("renders every menu item, with the first active by default", () => {
    render(<App />);
    const portfolio = screen.getByRole("button", { name: "Portfolio" });
    expect(portfolio).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Watchlists" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("marks a clicked menu item active instead", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Watchlists" }));

    expect(screen.getByRole("button", { name: "Watchlists" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "Portfolio" })).not.toHaveAttribute("aria-current");
  });

  it("toggles the theme and persists the choice", () => {
    render(<App />);
    const toggle = screen.getByRole("button", { name: /switch to dark theme/i });

    fireEvent.click(toggle);

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("ec-theme")).toBe("dark");
    expect(screen.getByRole("button", { name: /switch to light theme/i })).toBeInTheDocument();
  });
});
