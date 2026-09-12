import { useState } from "react";
import Modal from "../core/Modal.jsx";
import { SelectField } from "../core/Field.jsx";
import Button from "../core/Button.jsx";
import Alert from "../core/Alert.jsx";
import { useApi } from "../../api/useApi.js";
import {
  updateDefaultCurrency,
  updateFxWarmupCurrencies,
  updateTransactionType,
} from "../../api/identity.js";
import CURRENCIES from "../../config/currencies.json";
import "./SettingsModal.css";

/** Matches equicast_core.user_profiles.DEFAULT_FX_WARMUP_CURRENCIES — used
 * only as this form's fallback when `profile.fx_warmup_currencies` hasn't
 * loaded yet (the same "seed from the backend default until we know
 * otherwise" reasoning as `currency`/`transactionType` below). */
const DEFAULT_FX_WARMUP_CURRENCIES = ["GBP", "USD", "EUR"];

/**
 * Opened from UserMenu's "Settings" item. Three settings: default_currency
 * (options from the bundled currencies.json — no API call to fetch them,
 * see identity.js's updateDefaultCurrency doc — rather than a closed
 * `<select>` fetched at runtime), transaction_type (a single global
 * setting governing how every holding across every account/pie records
 * transactions — see equicast_core.transactions module docstring; the
 * backend rejects the change with a 409 once the user has any transaction
 * recorded anywhere, surfaced here as `error`), and fx_warmup_currencies
 * (GitHub issue #149 — which currencies the login-time FX warm-up, see
 * utils/fxWarmup.js, pairs against `default_currency`).
 *
 * Each setting saves independently (its own PATCH) so changing one doesn't
 * require re-submitting the others, and a transaction_type 409 doesn't
 * block a currency/warm-up-list change made in the same visit.
 */
function SettingsModal({ open, onClose, profile, onSaved }) {
  const api = useApi();
  const [currency, setCurrency] = useState(profile?.default_currency ?? CURRENCIES[0].code);
  const [transactionType, setTransactionType] = useState(profile?.transaction_type ?? "AVERAGE");
  const [fxWarmupCurrencies, setFxWarmupCurrencies] = useState(
    profile?.fx_warmup_currencies ?? DEFAULT_FX_WARMUP_CURRENCIES
  );
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const toggleFxWarmupCurrency = (code) => {
    setFxWarmupCurrencies((current) =>
      current.includes(code) ? current.filter((c) => c !== code) : [...current, code]
    );
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);

    const currencyChanged = currency !== (profile?.default_currency ?? CURRENCIES[0].code);
    const transactionTypeChanged = transactionType !== (profile?.transaction_type ?? "AVERAGE");
    const originalFxWarmupCurrencies = profile?.fx_warmup_currencies ?? DEFAULT_FX_WARMUP_CURRENCIES;
    const fxWarmupCurrenciesChanged =
      JSON.stringify([...fxWarmupCurrencies].sort()) !==
      JSON.stringify([...originalFxWarmupCurrencies].sort());

    Promise.resolve(currencyChanged ? updateDefaultCurrency(api, currency) : profile)
      .then((updated) =>
        transactionTypeChanged ? updateTransactionType(api, transactionType) : updated
      )
      .then((updated) =>
        fxWarmupCurrenciesChanged ? updateFxWarmupCurrencies(api, fxWarmupCurrencies) : updated
      )
      .then((updated) => {
        onSaved(updated);
        onClose();
      })
      .catch((err) => setError(err.message ?? "Couldn't update your settings."))
      .finally(() => setIsSaving(false));
  };

  return (
    <Modal open={open} onClose={onClose} title="Settings">
      <form onSubmit={handleSubmit} className="ec-form">
        {error && <Alert tone="danger">{error}</Alert>}
        <SelectField
          id="settings-default-currency"
          label="Default currency"
          value={currency}
          onChange={(event) => setCurrency(event.target.value)}
          hint="Used to value your accounts consistently across currencies."
        >
          {CURRENCIES.map((option) => (
            <option key={option.code} value={option.code}>
              {option.code} — {option.name}
            </option>
          ))}
        </SelectField>
        <SelectField
          id="settings-transaction-type"
          label="Transaction type"
          value={transactionType}
          onChange={(event) => setTransactionType(event.target.value)}
          hint="AVERAGE tracks one running average cost per holding; TRANSACTION keeps every buy/sell separately. Locked once you have any transaction recorded."
        >
          <option value="AVERAGE">Average cost</option>
          <option value="TRANSACTION">Per-transaction</option>
        </SelectField>
        <div className="ec-field">
          <span className="ec-field-label">FX warm-up currencies</span>
          <div className="ec-settings-fx-warmup-list">
            {CURRENCIES.map((option) => (
              <label key={option.code} className="ec-settings-fx-warmup-item">
                <input
                  type="checkbox"
                  checked={fxWarmupCurrencies.includes(option.code)}
                  onChange={() => toggleFxWarmupCurrency(option.code)}
                />
                {option.code}
              </label>
            ))}
          </div>
          <span className="ec-field-hint">
            Pre-warmed against your default currency when you sign in, so adding a transaction in
            one of these doesn&rsquo;t wait on a fresh FX lookup.
          </span>
        </div>
        <div className="ec-form-actions">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" isLoading={isSaving}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export default SettingsModal;
