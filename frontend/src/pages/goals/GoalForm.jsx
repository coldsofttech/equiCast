import { useState } from "react";
import { TextField, SelectField } from "../../components/core/Field.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import { GOAL_PURPOSE_LABELS, PURPOSE_CHOICES } from "../../config/goalPurposes.js";
import "./Goals.css";

const EMPTY_VALUES = {
  name: "",
  purpose: PURPOSE_CHOICES[0],
  custom_purpose: "",
  target_amount: "",
  target_date: "",
  account_ids: [],
  pie_ids: [],
};

/**
 * Shared create/edit body for GoalsListPage's "New goal"/"Edit goal"
 * drawers — same single-`values`-object pattern as AccountForm.jsx. Purpose
 * is a closed `<select>` (unlike account_type/currency's open `<datalist>`
 * — see AccountForm.jsx — because purpose *is* a real backend enum, see
 * equicast_core.goals.PURPOSE_CHOICES), revealing a `custom_purpose` text
 * field only when "other" is picked.
 *
 * The account/pie mapping picker excludes anything in `claimedAccountIds`/
 * `claimedPieIds` (ids already mapped to a *different* goal — computed by
 * the caller from the full goals list, so it never includes this goal's
 * own current mapping when editing). Checking an account auto-unchecks any
 * of its own pies (and disables them) — mapping both would double-count
 * that pie's holdings, and the backend rejects it (see backend/goals/
 * views.py's `_validate_mapping`) — so the form prevents it up front
 * instead of surfacing a 400 after submit.
 *
 * @param {{ initialValues?: object, accounts: import("../../api/accounts.js").Account[], claimedAccountIds: Set<string>, claimedPieIds: Set<string>, onSubmit: (values: object) => void, onCancel: () => void, isSubmitting: boolean, error: string|null }} props
 */
function GoalForm({
  initialValues,
  accounts,
  claimedAccountIds,
  claimedPieIds,
  onSubmit,
  onCancel,
  isSubmitting,
  error,
}) {
  const [values, setValues] = useState({
    ...EMPTY_VALUES,
    ...initialValues,
    account_ids: initialValues?.account_ids ?? [],
    pie_ids: initialValues?.pie_ids ?? [],
  });

  const setField = (field) => (event) =>
    setValues((current) => ({ ...current, [field]: event.target.value }));

  const toggleAccount = (accountId, pieIds) => {
    setValues((current) => {
      const isMapped = current.account_ids.includes(accountId);
      return {
        ...current,
        account_ids: isMapped
          ? current.account_ids.filter((id) => id !== accountId)
          : [...current.account_ids, accountId],
        // Checking an account supersedes its own pies — see docstring.
        pie_ids: isMapped ? current.pie_ids : current.pie_ids.filter((id) => !pieIds.includes(id)),
      };
    });
  };

  const togglePie = (pieId) => {
    setValues((current) => ({
      ...current,
      pie_ids: current.pie_ids.includes(pieId)
        ? current.pie_ids.filter((id) => id !== pieId)
        : [...current.pie_ids, pieId],
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit({
      ...values,
      target_amount: Number(values.target_amount),
      target_date: values.target_date || null,
      custom_purpose: values.purpose === "other" ? values.custom_purpose : null,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="ec-form">
      {error && <Alert tone="danger">{error}</Alert>}
      <TextField id="goal-name" label="Name" required value={values.name} onChange={setField("name")} />
      <SelectField id="goal-purpose" label="Purpose" value={values.purpose} onChange={setField("purpose")}>
        {PURPOSE_CHOICES.map((purpose) => (
          <option key={purpose} value={purpose}>
            {GOAL_PURPOSE_LABELS[purpose]}
          </option>
        ))}
      </SelectField>
      {values.purpose === "other" && (
        <TextField
          id="goal-custom-purpose"
          label="Describe the purpose"
          required
          value={values.custom_purpose}
          onChange={setField("custom_purpose")}
        />
      )}
      <TextField
        id="goal-target-amount"
        label="Target amount"
        type="number"
        min="0"
        step="0.01"
        required
        value={values.target_amount}
        onChange={setField("target_amount")}
        hint="In your default currency (see Settings)."
      />
      <TextField
        id="goal-target-date"
        label="Target date"
        type="date"
        value={values.target_date ?? ""}
        onChange={setField("target_date")}
        hint="Optional."
      />

      <div className="ec-field">
        <span className="ec-field-label">Map accounts / pies</span>
        <div className="ec-goal-mapping">
          {accounts.length === 0 && <p className="ec-goal-mapping-empty">No accounts yet.</p>}
          {accounts.map((account) => {
            const pies = account.pies ?? [];
            const pieIds = pies.map((pie) => pie.id);
            const accountChecked = values.account_ids.includes(account.id);
            const accountDisabled = claimedAccountIds.has(account.id);
            return (
              <div key={account.id} className="ec-goal-mapping-account">
                <label className="ec-goal-mapping-row">
                  <input
                    type="checkbox"
                    checked={accountChecked}
                    disabled={accountDisabled}
                    onChange={() => toggleAccount(account.id, pieIds)}
                  />
                  {account.name}
                  {accountDisabled && <span className="ec-goal-mapping-claimed">already in another goal</span>}
                </label>
                {pies.map((pie) => {
                  const pieDisabled = accountChecked || claimedPieIds.has(pie.id);
                  return (
                    <label key={pie.id} className="ec-goal-mapping-row ec-goal-mapping-row--nested">
                      <input
                        type="checkbox"
                        checked={values.pie_ids.includes(pie.id)}
                        disabled={pieDisabled}
                        onChange={() => togglePie(pie.id)}
                      />
                      {pie.name}
                      {!accountChecked && claimedPieIds.has(pie.id) && (
                        <span className="ec-goal-mapping-claimed">already in another goal</span>
                      )}
                    </label>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

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

export default GoalForm;
