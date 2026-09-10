import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth0 } from "@auth0/auth0-react";
import { updateDefaultCurrency, updateFxWarmupCurrencies } from "../../api/identity.js";
import SettingsModal from "./SettingsModal.jsx";

vi.mock("@auth0/auth0-react", () => ({ useAuth0: vi.fn() }));
vi.mock("../../api/identity.js", () => ({
  updateDefaultCurrency: vi.fn(),
  updateTransactionType: vi.fn(),
  updateFxWarmupCurrencies: vi.fn(),
}));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("SettingsModal", () => {
  it("pre-selects the profile's current default currency", () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });

    render(
      <SettingsModal
        open
        onClose={vi.fn()}
        profile={{ default_currency: "EUR" }}
        onSaved={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Default currency")).toHaveValue("EUR");
  });

  it("saves the selected currency and calls onSaved/onClose", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    const updated = { user_id: "auth0|abc", default_currency: "INR" };
    vi.mocked(updateDefaultCurrency).mockResolvedValue(updated);
    const onSaved = vi.fn();
    const onClose = vi.fn();

    render(
      <SettingsModal open onClose={onClose} profile={{ default_currency: "GBP" }} onSaved={onSaved} />
    );
    fireEvent.change(screen.getByLabelText("Default currency"), { target: { value: "INR" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(updated));
    expect(updateDefaultCurrency).toHaveBeenCalledWith(expect.any(Function), "INR");
    expect(onClose).toHaveBeenCalled();
  });

  it("shows an error and keeps the modal open on failure", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    vi.mocked(updateDefaultCurrency).mockRejectedValue(new Error("Nope."));
    const onClose = vi.fn();

    render(
      <SettingsModal open onClose={onClose} profile={{ default_currency: "GBP" }} onSaved={vi.fn()} />
    );
    fireEvent.change(screen.getByLabelText("Default currency"), { target: { value: "INR" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Nope.");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("pre-checks the profile's current fx_warmup_currencies", () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });

    render(
      <SettingsModal
        open
        onClose={vi.fn()}
        profile={{ default_currency: "GBP", fx_warmup_currencies: ["GBP", "INR"] }}
        onSaved={vi.fn()}
      />
    );

    expect(screen.getByRole("checkbox", { name: "INR" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "USD" })).not.toBeChecked();
  });

  it("saves a changed fx_warmup_currencies selection", async () => {
    vi.mocked(useAuth0).mockReturnValue({ getAccessTokenSilently: vi.fn() });
    const updated = { user_id: "auth0|abc", fx_warmup_currencies: ["GBP", "USD"] };
    vi.mocked(updateFxWarmupCurrencies).mockResolvedValue(updated);
    const onSaved = vi.fn();
    const onClose = vi.fn();

    render(
      <SettingsModal
        open
        onClose={onClose}
        profile={{ default_currency: "GBP", fx_warmup_currencies: ["GBP"] }}
        onSaved={onSaved}
      />
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "USD" }));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(updated));
    expect(updateFxWarmupCurrencies).toHaveBeenCalledWith(expect.any(Function), ["GBP", "USD"]);
    expect(onClose).toHaveBeenCalled();
  });
});
