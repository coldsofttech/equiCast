import { useState } from "react";
import { TextField, TextAreaField } from "../../components/core/Field.jsx";
import IconPicker from "../../components/core/IconPicker.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import ACCOUNT_TYPE_SUGGESTIONS from "../../config/accountTypes.json";
import CURRENCIES from "../../config/currencies.json";
import { ACCOUNT_ICON_OPTIONS, DEFAULT_ACCOUNT_ICON } from "../../config/accountIcons.js";

/**
 * Shared create/edit body for AccountsListPage's "New account" drawer and
 * AccountDetailPage's "Edit" drawer. `account_type`/`currency` have no
 * backend enum (see REQUIRED_CREATE_FIELDS in backend/accounts/views.py) —
 * free text with a `<datalist>` of common values rather than a closed
 * `<select>`, so a caller isn't blocked from an account type/currency this
 * list doesn't happen to include. The suggestion lists come from the same
 * config/*.json files as the Settings default-currency picker (see
 * SettingsModal.jsx), not a separate hardcoded array here.
 *
 * `defaultCurrency` (the caller's own profile.default_currency, see
 * useCurrentUser) seeds the currency field for a brand new account; it's
 * overridden by `initialValues.currency` when editing an existing one.
 */
const CURRENCY_SUGGESTIONS = CURRENCIES.map((currency) => currency.code);

const EMPTY_VALUES = {
  name: "",
  description: "",
  account_type: "",
  currency: "",
  icon: DEFAULT_ACCOUNT_ICON,
};

function AccountForm({ initialValues, defaultCurrency, onSubmit, onCancel, isSubmitting, error }) {
  const [values, setValues] = useState({
    ...EMPTY_VALUES,
    currency: defaultCurrency ?? EMPTY_VALUES.currency,
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
      <TextField
        id="account-currency"
        label="Currency"
        required
        list="currency-suggestions"
        value={values.currency}
        onChange={setField("currency")}
        hint="ISO code, e.g. GBP, USD, EUR."
      />
      <datalist id="currency-suggestions">
        {CURRENCY_SUGGESTIONS.map((option) => (
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
