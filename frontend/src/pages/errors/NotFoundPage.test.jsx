import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { getMe } from "../../api/identity.js";
import NotFoundPage from "./NotFoundPage.jsx";

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

describe("NotFoundPage", () => {
  it("renders a plain-language heading and a way back to the dashboard", () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Back to dashboard" })).toBeInTheDocument();
  });

  it("navigates to /dashboard when the action is clicked", () => {
    render(
      <MemoryRouter initialEntries={["/nope"]}>
        <Routes>
          <Route path="/dashboard" element={<p>Dashboard content</p>} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole("button", { name: "Back to dashboard" }));

    expect(screen.getByText("Dashboard content")).toBeInTheDocument();
  });

  it("keeps the normal Topbar (search, currency, account menu), since it's only ever reached signed in", async () => {
    render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>
    );

    expect(screen.getByLabelText("Search tickers")).toBeInTheDocument();
    expect(await screen.findByTitle("Default currency")).toHaveTextContent("USD");
    expect(screen.getByLabelText("Account")).toBeInTheDocument();
  });
});
