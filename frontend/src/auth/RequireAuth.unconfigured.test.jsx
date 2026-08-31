import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import RequireAuth from "./RequireAuth.jsx";

// Separate file so this can fix isAuth0Configured to false for every test
// here, while RequireAuth.test.jsx fixes it to true — see that file's
// comment for why one file can't easily cover both.
vi.mock("./auth0Config.js", () => ({ isAuth0Configured: false }));
vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RequireAuth (Auth0 not configured)", () => {
  it("shows a not-configured message without ever calling useAuth0", () => {
    render(
      <RequireAuth>
        <div>secret</div>
      </RequireAuth>
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/auth0 isn't configured/i);
    expect(useAuth0).not.toHaveBeenCalled();
  });
});
