import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import HideBalancesToggle from "./HideBalancesToggle.jsx";

beforeEach(() => {
  document.documentElement.setAttribute("data-hide-balances", "false");
  localStorage.clear();
});

afterEach(() => {
  document.documentElement.removeAttribute("data-hide-balances");
});

describe("HideBalancesToggle", () => {
  it("initializes from the DOM's current data-hide-balances", () => {
    render(<HideBalancesToggle />);
    expect(screen.getByRole("button", { name: /hide balances/i })).toBeInTheDocument();
  });

  it("sets data-hide-balances and persists the choice on click", () => {
    render(<HideBalancesToggle />);

    fireEvent.click(screen.getByRole("button", { name: /hide balances/i }));

    expect(document.documentElement.getAttribute("data-hide-balances")).toBe("true");
    expect(localStorage.getItem("ec-hide-balances")).toBe("true");
    expect(screen.getByRole("button", { name: /show balances/i })).toBeInTheDocument();
  });

  it("flips back to shown on a second click", () => {
    render(<HideBalancesToggle />);

    const button = () => screen.getByRole("button");
    fireEvent.click(button());
    fireEvent.click(button());

    expect(document.documentElement.getAttribute("data-hide-balances")).toBe("false");
    expect(localStorage.getItem("ec-hide-balances")).toBe("false");
  });
});
