import { useState } from "react";
import { TextField, SelectField, TextAreaField } from "../../components/core/Field.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";

/**
 * Shared create/edit body for AccountsListPage's "New account" modal and
 * AccountDetailPage's "Edit" modal. `account_type`/`currency` have no
 * backend enum (see REQUIRED_CREATE_FIELDS in backend/accounts/views.py) —
 * free text with a `<datalist>` of common values rather than a closed
 * `<select>`, so a caller isn't blocked from an account type/currency this
 * list doesn't happen to include.
 */
const ACCOUNT_TYPE_SUGGESTIONS = ["ISA", "GIA", "SIPP", "LISA", "Trading"];
const CURRENCY_SUGGESTIONS = ["GBP", "USD", "EUR", "JPY", "CHF"];

const EMPTY_VALUES = {
  name: "",
  description: "",
  account_type: "",
  currency: "",
  transaction_type: "AVERAGE",
};

function AccountForm({ initialValues, onSubmit, onCancel, isSubmitting, error }) {
  const [values, setValues] = useState({ ...EMPTY_VALUES, ...initialValues });

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
        required
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
      <SelectField
        id="account-transaction-type"
        label="Transaction type"
        required
        value={values.transaction_type}
        onChange={setField("transaction_type")}
        hint="AVERAGE tracks one running average cost per holding; TRANSACTION keeps every buy/sell separately. Locked once the account has recorded transactions."
      >
        <option value="AVERAGE">Average cost</option>
        <option value="TRANSACTION">Per-transaction</option>
      </SelectField>
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
