import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import ThemeToggle from "./ThemeToggle.jsx";

beforeEach(() => {
  document.documentElement.setAttribute("data-theme", "light");
  localStorage.clear();
});

afterEach(() => {
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeToggle", () => {
  it("initializes from the DOM's current data-theme", () => {
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: /switch to dark theme/i })).toBeInTheDocument();
  });

  it("flips data-theme and persists the choice on click", () => {
    render(<ThemeToggle />);

    fireEvent.click(screen.getByRole("button", { name: /switch to dark theme/i }));

    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("ec-theme")).toBe("dark");
    expect(screen.getByRole("button", { name: /switch to light theme/i })).toBeInTheDocument();
  });

  it("flips back to light on a second click", () => {
    render(<ThemeToggle />);

    const button = () => screen.getByRole("button");
    fireEvent.click(button());
    fireEvent.click(button());

    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(localStorage.getItem("ec-theme")).toBe("light");
  });
});
