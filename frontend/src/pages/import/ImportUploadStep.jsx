import { useState } from "react";
import { SelectField } from "../../components/core/Field.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import { useApi } from "../../api/useApi.js";
import { previewImport } from "../../api/transactions.js";
import "./ImportPage.css";

/**
 * First wizard step: pick a preset and upload a file, then call
 * `previewImport` — see backend/transactions/import_views.py's
 * ImportPreviewView. The Trading 212 export steps are shown inline rather
 * than only in docs/importing-transactions.md, so a user doesn't have to
 * leave the page to find them.
 */
function ImportUploadStep({ onParsed, onCancel }) {
  const api = useApi();
  const [preset, setPreset] = useState("trading212");
  const [file, setFile] = useState(null);
  const [error, setError] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  const handlePresetChange = (event) => {
    setPreset(event.target.value);
    setFile(null);
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!file) {
      setError("Choose a file to import.");
      return;
    }
    setIsUploading(true);
    setError(null);
    previewImport(api, file, preset)
      .then((preview) => onParsed(preview))
      .catch((err) => setError(err.message ?? "Couldn't parse this file."))
      .finally(() => setIsUploading(false));
  };

  return (
    <form onSubmit={handleSubmit} className="ec-form ec-import-step">
      {error && <Alert tone="danger">{error}</Alert>}
      <SelectField id="import-preset" label="Source" value={preset} onChange={handlePresetChange}>
        <option value="trading212">Trading 212 export</option>
        <option value="generic">Generic CSV</option>
      </SelectField>

      {preset === "trading212" ? (
        <Alert tone="info">
          In the Trading 212 app: <strong>Settings → History → Export</strong>, pick the time
          period, and under <strong>Include data</strong> check <strong>Orders</strong> and{" "}
          <strong>Transactions</strong>. <strong>Dividends</strong> and <strong>Interest</strong>{" "}
          can be left either way — equicast ignores those rows and backfills dividends itself.
        </Alert>
      ) : (
        <Alert tone="info">
          Columns required: <code>date, ticker, type, no_of_shares, price_native</code>.
          Optional: <code>asset_class, currency, fx_rate, external_id</code>. <code>type</code>{" "}
          must be BUY or SELL — dividends aren&rsquo;t imported, equicast backfills them
          automatically once a position exists.
        </Alert>
      )}

      <div className="ec-field">
        <label htmlFor="import-file" className="ec-field-label">
          File
        </label>
        <input
          id="import-file"
          type="file"
          accept=".csv"
          className="ec-input"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </div>

      <div className="ec-form-actions">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isUploading}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" isLoading={isUploading}>
          Continue
        </Button>
      </div>
    </form>
  );
}

export default ImportUploadStep;
