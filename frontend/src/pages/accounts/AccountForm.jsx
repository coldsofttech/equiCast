import { useState } from "react";
import { TextField, TextAreaField, SelectField } from "../../components/core/Field.jsx";
import IconPicker from "../../components/core/IconPicker.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import ACCOUNT_TYPES from "../../config/accountTypes.json";
import { ACCOUNT_ICON_OPTIONS, DEFAULT_ACCOUNT_ICON } from "../../config/accountIcons.js";
import { ACCOUNT_VENDOR_SUGGESTIONS } from "../../config/accountVendors.js";

/**
 * Shared create/edit body for AccountsListPage's "New account" drawer and
 * AccountDetailPage's "Edit" drawer. `account_type` — a.k.a. wrapper_type
 * (GitHub issue #94) — is a closed `<select>` now that tax logic branches
 * on it (see ACCOUNT_TYPES in backend/accounts/views.py, kept in sync with
 * this bundled list the same way identity/views.py's SUPPORTED_CURRENCIES
 * is kept in sync with config/currencies.json).
 *
 * No currency field — removed (GitHub issues #98/#115): every real money
 * figure is already valued in the user's own `default_currency` (see
 * Settings' default-currency picker), so there was nothing left for a
 * per-account currency to mean.
 */
//: Full names for ACCOUNT_TYPES's codes, displayed in the picker — the
//: stored value is still the bare code (matches backend's ACCOUNT_TYPES in
//: backend/accounts/views.py).
const ACCOUNT_TYPE_LABELS = {
  ISA: "Individual Savings Account (ISA)",
  GIA: "General Investment Account (GIA)",
  SIPP: "Self-Invested Personal Pension (SIPP)",
  LISA: "Lifetime ISA (LISA)",
  JISA: "Junior ISA (JISA)",
};

const EMPTY_VALUES = {
  name: "",
  description: "",
  account_type: ACCOUNT_TYPES[0],
  icon: DEFAULT_ACCOUNT_ICON,
  vendor: "",
};

function AccountForm({ initialValues, onSubmit, onCancel, isSubmitting, error }) {
  const [values, setValues] = useState({
    ...EMPTY_VALUES,
    ...initialValues,
    // `vendor` is optional and stored as `null` when unset (see
    // backend/accounts/views.py's OPTIONAL_CREATE_FIELDS) — coalesced to ""
    // here so the input below stays a controlled component.
    vendor: initialValues?.vendor ?? "",
  });

  const setField = (field) => (event) =>
    setValues((current) => ({ ...current, [field]: event.target.value }));

  const handleSubmit = (event) => {
    event.preventDefault();
    // Trim and fold a blank vendor back to `null` — matches what an account
    // without one already stores server-side (see AccountsClient.create_account's
    // `vendor: str | None = None`), rather than persisting an empty string.
    const vendor = values.vendor.trim();
    onSubmit({ ...values, vendor: vendor === "" ? null : vendor });
  };

  return (
    <form onSubmit={handleSubmit} className="ec-form">
      {error && <Alert tone="danger">{error}</Alert>}
      <TextField
        id="account-name"
        label="Name"
        required
        value={values.name}
        onChange={setField("name")}
      />
      <TextAreaField
        id="account-description"
        label="Description"
        value={values.description}
        onChange={setField("description")}
      />
      <SelectField
        id="account-type"
        label="Account type"
        required
        value={values.account_type}
        onChange={setField("account_type")}
        hint="Which UK tax wrapper this account is."
      >
        {ACCOUNT_TYPES.map((option) => (
          <option key={option} value={option}>
            {ACCOUNT_TYPE_LABELS[option] ?? option}
          </option>
        ))}
      </SelectField>
      <IconPicker
        id="account-icon"
        label="Icon"
        icons={ACCOUNT_ICON_OPTIONS}
        value={values.icon}
        onChange={(icon) => setValues((current) => ({ ...current, icon }))}
        hint="Optional — defaults to a bank icon if not set."
      />
      <TextField
        id="account-vendor"
        label="Vendor"
        list="account-vendor-suggestions"
        value={values.vendor}
        onChange={setField("vendor")}
        hint="Optional — the platform or broker this account is held with, e.g. Trading212, Chip."
      />
      <datalist id="account-vendor-suggestions">
        {ACCOUNT_VENDOR_SUGGESTIONS.map((vendor) => (
          <option key={vendor} value={vendor} />
        ))}
      </datalist>
      <div className="ec-form-actions">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" isLoading={isSubmitting}>
          Save
        </Button>
      </div>
    </form>
  );
}

export default AccountForm;
