import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { getMe } from "../../api/identity.js";
import Topbar from "./Topbar.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/identity.js", () => ({ getMe: vi.fn() }));

beforeEach(() => {
  vi.mocked(getMe).mockResolvedValue({ default_currency: "USD" });
  vi.mocked(useAuth0).mockReturnValue({
    isAuthenticated: true,
    user: { name: "Jane Doe", email: "jane@example.com" },
    getAccessTokenSilently: vi.fn(),
    logout: vi.fn(),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(navigator, "onLine", { configurable: true, value: true });
});

describe("Topbar", () => {
  it("has no offline banner while online", () => {
    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>
    );

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows an offline banner instead of replacing the page when offline", () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });

    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>
    );

    expect(screen.getByRole("status")).toHaveTextContent(/you.re offline/i);
    // The rest of Topbar's chrome is still there — nothing was swapped out.
    expect(screen.getByLabelText("Search tickers")).toBeInTheDocument();
  });

  it("clears the banner once the browser reports back online", () => {
    Object.defineProperty(navigator, "onLine", { configurable: true, value: false });

    render(
      <MemoryRouter>
        <Topbar />
      </MemoryRouter>
    );

    expect(screen.getByRole("status")).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(new Event("online"));
    });

    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
