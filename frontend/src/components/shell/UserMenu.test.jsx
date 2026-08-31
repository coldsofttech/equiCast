import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import UserMenu from "./UserMenu.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));

function mockUser(user, logout = vi.fn()) {
  vi.mocked(useAuth0).mockReturnValue({ user, logout });
  return logout;
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("UserMenu", () => {
  it("shows initials from the user's name and opens the panel on click", () => {
    mockUser({ name: "Ada Lovelace", email: "ada@example.com" });

    render(<UserMenu />);

    expect(screen.getByText("AL")).toBeInTheDocument();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /account/i }));

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
  });

  it("falls back to the email when no name is set", () => {
    mockUser({ email: "ada@example.com" });

    render(<UserMenu />);
    fireEvent.click(screen.getByRole("button", { name: /account/i }));

    expect(screen.getByText("ada@example.com")).toBeInTheDocument();
  });

  it("closes on Escape", () => {
    mockUser({ name: "Ada Lovelace", email: "ada@example.com" });

    render(<UserMenu />);
    fireEvent.click(screen.getByRole("button", { name: /account/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes on an outside click", () => {
    mockUser({ name: "Ada Lovelace", email: "ada@example.com" });

    render(<UserMenu />);
    fireEvent.click(screen.getByRole("button", { name: /account/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();

    fireEvent.mouseDown(document.body);

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("calls logout with the app's origin on sign-out", () => {
    const logout = mockUser({ name: "Ada Lovelace", email: "ada@example.com" });

    render(<UserMenu />);
    fireEvent.click(screen.getByRole("button", { name: /account/i }));
    fireEvent.click(screen.getByRole("menuitem", { name: /log out/i }));

    expect(logout).toHaveBeenCalledWith({ logoutParams: { returnTo: window.location.origin } });
  });
});
