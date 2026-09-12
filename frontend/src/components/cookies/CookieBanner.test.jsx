import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import CookieBanner, { openCookiePreferences } from "./CookieBanner.jsx";
import { getCookieConsent } from "../../utils/cookieConsent.js";

afterEach(() => {
  localStorage.clear();
});

function renderBanner() {
  return render(
    <MemoryRouter>
      <CookieBanner />
    </MemoryRouter>
  );
}

describe("CookieBanner", () => {
  it("shows the banner when no choice has been made yet", () => {
    renderBanner();

    expect(screen.getByRole("dialog", { name: "Cookie notice" })).toBeInTheDocument();
  });

  it("hides itself and accepts everything when Accept all is clicked", () => {
    renderBanner();

    fireEvent.click(screen.getByRole("button", { name: "Accept all" }));

    expect(screen.queryByRole("dialog", { name: "Cookie notice" })).not.toBeInTheDocument();
    expect(getCookieConsent()).toEqual({ analytics: true });
  });

  it("hides itself and rejects analytics when Reject non-essential is clicked", () => {
    renderBanner();

    fireEvent.click(screen.getByRole("button", { name: "Reject non-essential" }));

    expect(screen.queryByRole("dialog", { name: "Cookie notice" })).not.toBeInTheDocument();
    expect(getCookieConsent()).toEqual({ analytics: false });
  });

  it("opens the preferences panel with necessary/functional locked and analytics off by default", () => {
    renderBanner();

    fireEvent.click(screen.getByRole("button", { name: "Manage preferences" }));

    expect(screen.getByRole("dialog", { name: "Cookie preferences" })).toBeInTheDocument();
    expect(screen.getAllByText("Always on")).toHaveLength(2);
    expect(screen.getByRole("checkbox", { name: "Analytics" })).not.toBeChecked();
  });

  it("saves only the analytics toggle from the preferences panel", () => {
    renderBanner();
    fireEvent.click(screen.getByRole("button", { name: "Manage preferences" }));

    fireEvent.click(screen.getByRole("checkbox", { name: "Analytics" }));
    fireEvent.click(screen.getByRole("button", { name: "Save preferences" }));

    expect(screen.queryByRole("dialog", { name: "Cookie preferences" })).not.toBeInTheDocument();
    expect(getCookieConsent()).toEqual({ analytics: true });
  });

  it("reopens the preferences panel via openCookiePreferences after a choice was already made", () => {
    renderBanner();
    fireEvent.click(screen.getByRole("button", { name: "Accept all" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    act(() => {
      openCookiePreferences();
    });

    expect(screen.getByRole("dialog", { name: "Cookie preferences" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Analytics" })).toBeChecked();
  });
});
