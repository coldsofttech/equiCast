import { useState } from "react";
import { TextField, TextAreaField } from "../../components/core/Field.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";

const EMPTY_VALUES = { name: "", description: "" };

/** Shared create/rename body for a custom watchlist — a system watchlist
 * (see backend/watchlists/views.py's SYSTEM_WATCHLISTS) has no form at all,
 * since it isn't user-edited. */
function WatchlistForm({ initialValues, onSubmit, onCancel, isSubmitting, error }) {
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
        id="watchlist-name"
        label="Name"
        required
        value={values.name}
        onChange={setField("name")}
      />
      <TextAreaField
        id="watchlist-description"
        label="Description"
        value={values.description}
        onChange={setField("description")}
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

export default WatchlistForm;
