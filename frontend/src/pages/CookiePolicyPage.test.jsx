import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import CookiePolicyPage from "./CookiePolicyPage.jsx";

describe("CookiePolicyPage", () => {
  it("renders the policy's three real categories", () => {
    render(
      <MemoryRouter>
        <CookiePolicyPage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Cookie Policy" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Strictly necessary/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Functional/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Analytics/ })).toBeInTheDocument();
  });

  it("dispatches the open-preferences event when the manage button is clicked", () => {
    render(
      <MemoryRouter>
        <CookiePolicyPage />
      </MemoryRouter>
    );
    const listener = vi.fn();
    window.addEventListener("ec:open-cookie-preferences", listener);

    fireEvent.click(screen.getByRole("button", { name: "Manage your cookie preferences" }));

    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener("ec:open-cookie-preferences", listener);
  });
});
