import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { getMe } from "../../api/identity.js";
import { useAccounts } from "../../api/useAccounts.js";
import { useGoals } from "../../api/useGoals.js";
import { submitSupportRequest } from "../../api/support.js";
import SupportPage from "./SupportPage.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/identity.js", () => ({ getMe: vi.fn() }));
vi.mock("../../api/useAccounts.js", () => ({ useAccounts: vi.fn() }));
vi.mock("../../api/useGoals.js", () => ({ useGoals: vi.fn() }));
vi.mock("../../api/support.js", () => ({ submitSupportRequest: vi.fn() }));

// jsdom has no IntersectionObserver — AppShell's stickyTitle needs one.
beforeEach(() => {
  vi.mocked(getMe).mockResolvedValue({ default_currency: "GBP" });
  vi.mocked(useAuth0).mockReturnValue({
    isAuthenticated: true,
    user: { name: "Jane Doe", email: "jane@example.com" },
    getAccessTokenSilently: vi.fn(),
    logout: vi.fn(),
  });
  vi.mocked(useAccounts).mockReturnValue({ accounts: [], isLoading: false, error: null });
  vi.mocked(useGoals).mockReturnValue({ goals: [], isLoading: false, error: null });
  global.IntersectionObserver = class {
    observe() {}
    disconnect() {}
  };
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SupportPage", () => {
  it("submits a query without a ticker field shown", async () => {
    vi.mocked(submitSupportRequest).mockResolvedValue({ detail: "Thanks — we've received this." });

    render(
      <MemoryRouter>
        <SupportPage />
      </MemoryRouter>
    );

    expect(screen.queryByLabelText("Ticker")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Details", { exact: false }), {
      target: { value: "How do I add a holding?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(submitSupportRequest).toHaveBeenCalledWith(expect.any(Function), {
        category: "query",
        description: "How do I add a holding?",
      })
    );
    expect(await screen.findByText("Thanks — we've received this.")).toBeInTheDocument();
  });

  it("shows a ticker field and includes it for a ticker-request", async () => {
    vi.mocked(submitSupportRequest).mockResolvedValue({ detail: "Thanks — we've received this." });

    render(
      <MemoryRouter>
        <SupportPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("What's this about?", { exact: false }), {
      target: { value: "ticker-request" },
    });
    fireEvent.change(screen.getByLabelText(/^Ticker/), {
      target: { value: "NVDA" },
    });
    fireEvent.change(screen.getByLabelText("Details", { exact: false }), {
      target: { value: "Please add NVDA." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(submitSupportRequest).toHaveBeenCalledWith(expect.any(Function), {
        category: "ticker-request",
        description: "Please add NVDA.",
        ticker: "NVDA",
      })
    );
  });

  it("requires a ticker (not a description) for a ticker-request", async () => {
    vi.mocked(submitSupportRequest).mockResolvedValue({ detail: "Thanks — we've received this." });

    render(
      <MemoryRouter>
        <SupportPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("What's this about?", { exact: false }), {
      target: { value: "ticker-request" },
    });
    expect(screen.getByLabelText(/^Ticker/)).toBeRequired();
    expect(screen.getByLabelText("Details", { exact: false })).not.toBeRequired();

    fireEvent.change(screen.getByLabelText(/^Ticker/), { target: { value: "NVDA" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(submitSupportRequest).toHaveBeenCalledWith(expect.any(Function), {
        category: "ticker-request",
        ticker: "NVDA",
      })
    );
  });

  it("defaults to Other and includes subject fields for incorrect-data", async () => {
    vi.mocked(submitSupportRequest).mockResolvedValue({ detail: "Thanks — we've received this." });

    render(
      <MemoryRouter>
        <SupportPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("What's this about?", { exact: false }), {
      target: { value: "incorrect-data" },
    });
    expect(screen.getByLabelText("What's affected?", { exact: false })).toHaveValue("other");
    expect(screen.getByLabelText("Which one?", { exact: false })).toHaveValue("Other");
    expect(screen.getByLabelText("Details", { exact: false })).toBeRequired();

    fireEvent.change(screen.getByLabelText("Details", { exact: false }), {
      target: { value: "The value looks wrong." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(submitSupportRequest).toHaveBeenCalledWith(expect.any(Function), {
        category: "incorrect-data",
        description: "The value looks wrong.",
        subject_type: "other",
        subject: "Other",
      })
    );
  });

  it("lists the user's own pies as subject options and resets on type change", async () => {
    vi.mocked(useAccounts).mockReturnValue({
      accounts: [
        {
          id: "acc-1",
          name: "My ISA",
          pies: [{ id: "pie-1", name: "Growth Pie" }],
          holdings: [{ id: "hold-1", ticker: "AAPL" }],
        },
      ],
      isLoading: false,
      error: null,
    });
    vi.mocked(submitSupportRequest).mockResolvedValue({ detail: "Thanks — we've received this." });

    render(
      <MemoryRouter>
        <SupportPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("What's this about?", { exact: false }), {
      target: { value: "incorrect-data" },
    });
    fireEvent.change(screen.getByLabelText("What's affected?", { exact: false }), {
      target: { value: "pie" },
    });

    const subjectSelect = screen.getByLabelText("Which one?", { exact: false });
    expect(subjectSelect).toHaveValue("Other");
    expect(screen.getByRole("option", { name: "Growth Pie (My ISA)" })).toBeInTheDocument();

    fireEvent.change(subjectSelect, { target: { value: "Growth Pie (My ISA)" } });
    fireEvent.change(screen.getByLabelText("Details", { exact: false }), {
      target: { value: "The invested amount looks wrong." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(submitSupportRequest).toHaveBeenCalledWith(expect.any(Function), {
        category: "incorrect-data",
        description: "The invested amount looks wrong.",
        subject_type: "pie",
        subject: "Growth Pie (My ISA)",
      })
    );
  });

  it("surfaces a submit error", async () => {
    vi.mocked(submitSupportRequest).mockRejectedValue(new Error("Request was throttled."));

    render(
      <MemoryRouter>
        <SupportPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("Details", { exact: false }), {
      target: { value: "How do I add a holding?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Request was throttled.");
  });
});
