import { useState } from "react";
import { TextField, TextAreaField } from "../../components/core/Field.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";

const EMPTY_VALUES = { name: "", description: "" };

/** Shared create/edit body for a pie — `account_id` is fixed by the
 * caller (AccountDetailPage), never edited here: it's immutable once a
 * pie exists (see backend/pies/views.py's UPDATABLE_FIELDS). */
function PieForm({ initialValues, onSubmit, onCancel, isSubmitting, error }) {
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
        id="pie-name"
        label="Name"
        required
        value={values.name}
        onChange={setField("name")}
      />
      <TextAreaField
        id="pie-description"
        label="Description"
        required
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

export default PieForm;
