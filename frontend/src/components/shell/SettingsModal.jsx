import { useState } from "react";
import Modal from "../core/Modal.jsx";
import { SelectField } from "../core/Field.jsx";
import Button from "../core/Button.jsx";
import Alert from "../core/Alert.jsx";
import { useApi } from "../../api/useApi.js";
import { updateDefaultCurrency } from "../../api/identity.js";
import CURRENCIES from "../../config/currencies.json";

/**
 * Opened from UserMenu's "Settings" item. The only setting so far is
 * default_currency — its options come from the bundled currencies.json
 * (no API call to fetch them, see identity.js's updateDefaultCurrency
 * doc) rather than a closed `<select>` fetched at runtime.
 */
function SettingsModal({ open, onClose, profile, onSaved }) {
  const api = useApi();
  const [currency, setCurrency] = useState(profile?.default_currency ?? CURRENCIES[0].code);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = (event) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    updateDefaultCurrency(api, currency)
      .then((updated) => {
        onSaved(updated);
        onClose();
      })
      .catch((err) => setError(err.message ?? "Couldn't update your default currency."))
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
