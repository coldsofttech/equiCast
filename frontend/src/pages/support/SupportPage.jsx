import { useState } from "react";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import { TextField, TextAreaField, SelectField } from "../../components/core/Field.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import { useApi } from "../../api/useApi.js";
import { useAccounts } from "../../api/useAccounts.js";
import { useGoals } from "../../api/useGoals.js";
import { submitSupportRequest } from "../../api/support.js";
import SUPPORT_CATEGORIES from "../../config/supportCategories.json";
import SUPPORT_SUBJECT_TYPES from "../../config/supportSubjectTypes.json";

//: "ticker-request" flips which of ticker/description is mandatory —
//: naming the ticker is the whole point of that category, while a
//: description is optional extra context. Matches backend/support/
//: views.py's SupportView.post.
const TICKER_REQUIRED_CATEGORY = "ticker-request";

//: "incorrect-data" requires saying *what's* wrong — a subject type
//: (account/pie/goal/holding/other) plus which specific one. Matches
//: backend/support/views.py's SupportView.post/SUBJECT_TYPES.
const INCORRECT_DATA_CATEGORY = "incorrect-data";

//: The subject-type dropdown's default and fallback — always present as
//: the first option in the subject/value dropdown too, so there's always a
//: valid selection even before any real accounts/pies/goals/holdings have
//: loaded, or when none of them fit.
const OTHER_SUBJECT = "Other";

const MAX_DESCRIPTION_LENGTH = 4000;

const EMPTY_VALUES = {
  category: SUPPORT_CATEGORIES[0].value,
  description: "",
  ticker: "",
  subjectType: SUPPORT_SUBJECT_TYPES[SUPPORT_SUBJECT_TYPES.length - 1].value,
  subject: OTHER_SUBJECT,
};

/**
 * The subject/value dropdown's options for a given subjectType, built from
 * the user's real accounts/pies/goals/holdings (accounts.js's Account
 * already nests pies and direct holdings, and each Pie its own holdings —
 * see accounts.js's Account/Pie/Holding typedefs — so pies/holdings are
 * flattened from `accounts` rather than fetched separately). "Other" is
 * always first/default, matching the subject-type dropdown's own default,
 * so there's always a valid selection regardless of what's loaded.
 */
function subjectOptionsFor(subjectType, accounts, goals) {
  const options = [OTHER_SUBJECT];
  if (subjectType === "account") {
    options.push(...accounts.map((account) => account.name));
  } else if (subjectType === "pie") {
    for (const account of accounts) {
      for (const pie of account.pies ?? []) {
        options.push(`${pie.name} (${account.name})`);
      }
    }
  } else if (subjectType === "goal") {
    options.push(...goals.map((goal) => goal.name));
  } else if (subjectType === "holding") {
    for (const account of accounts) {
      for (const holding of account.holdings ?? []) {
        options.push(`${holding.ticker} (${account.name})`);
      }
      for (const pie of account.pies ?? []) {
        for (const holding of pie.holdings ?? []) {
          options.push(`${holding.ticker} (${account.name} / ${pie.name})`);
        }
      }
    }
  }
  return options;
}

/**
 * GitHub issue #246: a help/support page that raises a GitHub issue in a
 * dedicated *private* repo (backend/support/views.py's SupportView —
 * coldsofttech/equicast-support, never the public equiCast repo, so no
 * submitted ticket is ever visible to other users or the internet). Shows
 * only a generic "thanks" confirmation on success, never the created
 * issue's URL/number — the user has no access to that repo to follow it
 * there anyway.
 */
function SupportPage() {
  const api = useApi();
  const { accounts } = useAccounts();
  const { goals } = useGoals();
  const [values, setValues] = useState(EMPTY_VALUES);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [succeeded, setSucceeded] = useState(false);

  const setField = (field) => (event) =>
    setValues((current) => ({ ...current, [field]: event.target.value }));

  // Switching subject type invalidates whatever was previously selected in
  // the subject dropdown (an account name is meaningless once "Pie" is
  // chosen) - reset it back to the same default the type dropdown itself
  // defaults to, rather than submitting a stale, mismatched value.
  const setSubjectType = (event) =>
    setValues((current) => ({
      ...current,
      subjectType: event.target.value,
      subject: OTHER_SUBJECT,
    }));

  const isTickerRequired = values.category === TICKER_REQUIRED_CATEGORY;
  const isIncorrectData = values.category === INCORRECT_DATA_CATEGORY;
  const subjectOptions = subjectOptionsFor(values.subjectType, accounts, goals);

  const handleSubmit = (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setSucceeded(false);

    const payload = { category: values.category };
    if (values.description.trim()) {
      payload.description = values.description.trim();
    }
    if (isTickerRequired && values.ticker.trim()) {
      payload.ticker = values.ticker.trim();
    }
    if (isIncorrectData) {
      payload.subject_type = values.subjectType;
      payload.subject = values.subject;
    }

    submitSupportRequest(api, payload)
      .then(() => {
        setValues(EMPTY_VALUES);
        setSucceeded(true);
      })
      .catch((err) => setError(err.message ?? "Couldn't submit this right now."))
      .finally(() => setIsSubmitting(false));
  };

  return (
    <AppShell
      eyebrow="Help"
      title="Support"
      subtitle="Ask a question, request a new ticker, or report something that looks wrong."
      footer={<SiteFooter />}
    >
      <form onSubmit={handleSubmit} className="ec-form">
        {error && <Alert tone="danger">{error}</Alert>}
        {succeeded && <Alert tone="success">Thanks — we've received this.</Alert>}
        <SelectField
          id="support-category"
          label="What's this about?"
          required
          value={values.category}
          onChange={setField("category")}
        >
          {SUPPORT_CATEGORIES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </SelectField>
        {isTickerRequired && (
          <TextField
            id="support-ticker"
            label="Ticker"
            required
            value={values.ticker}
            onChange={setField("ticker")}
          />
        )}
        {isIncorrectData && (
          <>
            <SelectField
              id="support-subject-type"
              label="What's affected?"
              required
              value={values.subjectType}
              onChange={setSubjectType}
            >
              {SUPPORT_SUBJECT_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </SelectField>
            <SelectField
              id="support-subject"
              label="Which one?"
              required
              value={values.subject}
              onChange={setField("subject")}
            >
              {subjectOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </SelectField>
          </>
        )}
        <TextAreaField
          id="support-description"
          label="Details"
          required={!isTickerRequired}
          rows={6}
          maxLength={MAX_DESCRIPTION_LENGTH}
          value={values.description}
          onChange={setField("description")}
          hint={
            isTickerRequired
              ? "Optional — anything else that helps (why it matters, exchange, etc.). Please don't include any sensitive information (passwords, account numbers, etc.)."
              : "Please don't include any sensitive information (passwords, account numbers, etc.)."
          }
        />
        <div className="ec-form-actions">
          <Button type="submit" variant="primary" isLoading={isSubmitting}>
            Submit
          </Button>
        </div>
      </form>
    </AppShell>
  );
}

export default SupportPage;
