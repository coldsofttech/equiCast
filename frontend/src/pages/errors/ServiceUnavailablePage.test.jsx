import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { getMe } from "../../api/identity.js";
import ServiceUnavailablePage from "./ServiceUnavailablePage.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/identity.js", () => ({ getMe: vi.fn() }));

// jsdom has no IntersectionObserver — AppShell's stickyTitle needs one.
beforeEach(() => {
  vi.mocked(getMe).mockRejectedValue(new Error("Couldn't load your profile."));
  vi.mocked(useAuth0).mockReturnValue({
    isAuthenticated: true,
    user: { name: "Jane Doe", email: "jane@example.com" },
    getAccessTokenSilently: vi.fn(),
    logout: vi.fn(),
  });
  global.IntersectionObserver = class {
    observe() {}
    disconnect() {}
  };
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ServiceUnavailablePage", () => {
  it("renders a plain-language heading and a retry action", () => {
    render(
      <MemoryRouter>
        <ServiceUnavailablePage />
      </MemoryRouter>
    );

    expect(
      screen.getByRole("heading", { name: "equiCast is temporarily unavailable" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("calls the caller's own onRetry instead of reloading when given one", () => {
    const onRetry = vi.fn();
    render(
      <MemoryRouter>
        <ServiceUnavailablePage onRetry={onRetry} />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("keeps the normal Topbar (search, account menu) even though the profile fetch itself is failing", () => {
    render(
      <MemoryRouter>
        <ServiceUnavailablePage />
      </MemoryRouter>
    );

    expect(screen.getByLabelText("Search tickers")).toBeInTheDocument();
    expect(screen.getByLabelText("Account")).toBeInTheDocument();
    // The currency badge depends on the very fetch that's failing, so it's
    // simply absent rather than broken.
    expect(screen.queryByTitle("Default currency")).not.toBeInTheDocument();
  });
});
