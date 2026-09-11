import { useState } from "react";
import { TextField, TextAreaField } from "../../components/core/Field.jsx";
import IconPicker from "../../components/core/IconPicker.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import ACCOUNT_TYPE_SUGGESTIONS from "../../config/accountTypes.json";
import { ACCOUNT_ICON_OPTIONS, DEFAULT_ACCOUNT_ICON } from "../../config/accountIcons.js";

/**
 * Shared create/edit body for AccountsListPage's "New account" drawer and
 * AccountDetailPage's "Edit" drawer. `account_type` has no backend enum
 * (see REQUIRED_CREATE_FIELDS in backend/accounts/views.py) — free text
 * with a `<datalist>` of common values rather than a closed `<select>`, so
 * a caller isn't blocked from an account type this list doesn't happen to
 * include.
 *
 * No currency field — removed (GitHub issues #98/#115): every real money
 * figure is already valued in the user's own `default_currency` (see
 * Settings' default-currency picker), so there was nothing left for a
 * per-account currency to mean.
 */
const EMPTY_VALUES = {
  name: "",
  description: "",
  account_type: "",
  icon: DEFAULT_ACCOUNT_ICON,
};

function AccountForm({ initialValues, onSubmit, onCancel, isSubmitting, error }) {
  const [values, setValues] = useState({
    ...EMPTY_VALUES,
    ...initialValues,
  });

  const setField = (field) => (event) =>
    setValues((current) => ({ ...current, [field]: event.target.value }));

  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit(values);
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
      <TextField
        id="account-type"
        label="Account type"
        required
        list="account-type-suggestions"
        value={values.account_type}
        onChange={setField("account_type")}
        hint="e.g. ISA, GIA, SIPP — whatever labels your accounts."
      />
      <datalist id="account-type-suggestions">
        {ACCOUNT_TYPE_SUGGESTIONS.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
      <IconPicker
        id="account-icon"
        label="Icon"
        icons={ACCOUNT_ICON_OPTIONS}
        value={values.icon}
        onChange={(icon) => setValues((current) => ({ ...current, icon }))}
        hint="Optional — defaults to a bank icon if not set."
      />
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
