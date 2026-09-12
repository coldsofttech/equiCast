import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { getMe } from "../../api/identity.js";
import GoalsPage from "./GoalsPage.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/identity.js", () => ({ getMe: vi.fn() }));

// jsdom has no IntersectionObserver — AppShell's stickyTitle needs one.
beforeEach(() => {
  vi.mocked(getMe).mockResolvedValue({ default_currency: "USD" });
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

describe("GoalsPage", () => {
  it("renders a placeholder heading and message", () => {
    render(
      <MemoryRouter>
        <GoalsPage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Goals" })).toBeInTheDocument();
    expect(screen.getByText(/on its way/i)).toBeInTheDocument();
  });
});
