import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import RequireAuth from "./RequireAuth.jsx";

// isAuth0Configured is fixed true for this whole file — see
// RequireAuth.unconfigured.test.jsx for the false case. A vi.mock factory
// runs once per test file, so a single file can't cover both without
// resorting to vi.resetModules()/dynamic import gymnastics for no real
// benefit over just splitting the file.
vi.mock("./auth0Config.js", () => ({ isAuth0Configured: true }));
vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("RequireAuth (Auth0 configured)", () => {
  it("shows a loading state while Auth0 initializes", () => {
    vi.mocked(useAuth0).mockReturnValue({
      isLoading: true,
      isAuthenticated: false,
      loginWithRedirect: vi.fn(),
      error: undefined,
    });

    render(
      <RequireAuth>
        <div>secret</div>
      </RequireAuth>
    );

    expect(screen.getByRole("status")).toHaveTextContent(/loading/i);
  });

  it("shows the sign-in screen when not authenticated, and starts login on click", () => {
    const loginWithRedirect = vi.fn();
    vi.mocked(useAuth0).mockReturnValue({
      isLoading: false,
      isAuthenticated: false,
      loginWithRedirect,
      error: undefined,
    });

    render(
      <RequireAuth>
        <div>secret</div>
      </RequireAuth>
    );

    fireEvent.click(screen.getByRole("button", { name: /log in/i }));
    expect(loginWithRedirect).toHaveBeenCalledWith(
      expect.objectContaining({
        appState: expect.objectContaining({ returnTo: expect.any(String) }),
      })
    );
  });

  it("shows a generic error message when Auth0 itself errored", () => {
    vi.mocked(useAuth0).mockReturnValue({
      isLoading: false,
      isAuthenticated: false,
      loginWithRedirect: vi.fn(),
      error: new Error("boom"),
    });

    render(
      <RequireAuth>
        <div>secret</div>
      </RequireAuth>
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/something went wrong/i);
  });

  it("renders children once authenticated", () => {
    vi.mocked(useAuth0).mockReturnValue({
      isLoading: false,
      isAuthenticated: true,
      loginWithRedirect: vi.fn(),
      error: undefined,
    });

    render(
      <RequireAuth>
        <div>secret</div>
      </RequireAuth>
    );

    expect(screen.getByText("secret")).toBeInTheDocument();
  });
});
