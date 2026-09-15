import { useState } from "react";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import { TextField, TextAreaField, SelectField } from "../../components/core/Field.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import { useApi } from "../../api/useApi.js";
import { submitSupportRequest } from "../../api/support.js";
import SUPPORT_CATEGORIES from "../../config/supportCategories.json";

//: Categories where a ticker field is actually relevant — shown/hidden
//: rather than always-present, since it's meaningless for a plain "query"/
//: "other" submission. Matches backend/support/views.py's CATEGORIES keys.
const TICKER_CATEGORIES = new Set(["ticker-request", "incorrect-data"]);

const MAX_DESCRIPTION_LENGTH = 4000;

const EMPTY_VALUES = {
  category: SUPPORT_CATEGORIES[0].value,
  description: "",
  ticker: "",
};

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
  const [values, setValues] = useState(EMPTY_VALUES);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [succeeded, setSucceeded] = useState(false);

  const setField = (field) => (event) =>
    setValues((current) => ({ ...current, [field]: event.target.value }));

  const handleSubmit = (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setSucceeded(false);

    const payload = {
      category: values.category,
      description: values.description.trim(),
    };
    if (TICKER_CATEGORIES.has(values.category) && values.ticker.trim()) {
      payload.ticker = values.ticker.trim();
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
        {TICKER_CATEGORIES.has(values.category) && (
          <TextField
            id="support-ticker"
            label="Ticker"
            value={values.ticker}
            onChange={setField("ticker")}
            hint="Optional — the ticker symbol this is about, if any."
          />
        )}
        <TextAreaField
          id="support-description"
          label="Details"
          required
          rows={6}
          maxLength={MAX_DESCRIPTION_LENGTH}
          value={values.description}
          onChange={setField("description")}
          hint="Please don't include any sensitive information (passwords, account numbers, etc.)."
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
