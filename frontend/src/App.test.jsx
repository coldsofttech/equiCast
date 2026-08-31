import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import App from "./App.jsx";

// No VITE_AUTH0_* env vars are set in the test environment, so
// RequireAuth's "not configured" branch is what actually renders here —
// see auth/RequireAuth.test.jsx / RequireAuth.unconfigured.test.jsx for
// the real gating-logic coverage (loading/unauthenticated/authenticated).
// This file only checks the routing shape: both a known and an unknown
// path land on the same gated root.
describe("App routing", () => {
  it("renders the auth gate at /", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/auth0 isn't configured/i);
  });

  it("redirects an unknown path back to /", () => {
    render(
      <MemoryRouter initialEntries={["/nope"]}>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/auth0 isn't configured/i);
  });
});
