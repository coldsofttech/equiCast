import Alert from "../../components/core/Alert.jsx";
import Button from "../../components/core/Button.jsx";
import "./ImportPage.css";

const STATUS_TONE = {
  created: "success",
  partial: "info",
  skipped: "info",
  error: "danger",
};

const STATUS_LABEL = {
  created: "Imported",
  partial: "Partially imported",
  skipped: "Skipped",
  error: "Failed",
};

/** Final wizard step: `commitImport`'s per-selection results (see
 * backend/transactions/import_views.py's ImportCommitView) — one failing
 * selection never means the whole batch failed, so this shows every
 * outcome individually rather than a single pass/fail banner. */
function ImportResultStep({ results, onDone }) {
  return (
    <div className="ec-form ec-import-step">
      <ul className="ec-import-results">
        {results.map((result) => (
          <li key={`${result.ticker}-${result.holding_id ?? "none"}`}>
            <Alert tone={STATUS_TONE[result.status] ?? "info"}>
              <strong>{result.ticker}</strong> — {STATUS_LABEL[result.status] ?? result.status}
              {result.detail ? `: ${result.detail}` : ""}
              {typeof result.created_count === "number" && (
                <>
                  {" "}
                  ({result.created_count} created
                  {result.skipped_duplicate_count
                    ? `, ${result.skipped_duplicate_count} already imported`
                    : ""}
                  )
                </>
              )}
            </Alert>
          </li>
        ))}
      </ul>
      <div className="ec-form-actions">
        <Button type="button" variant="primary" onClick={onDone}>
          Done
        </Button>
      </div>
    </div>
  );
}

export default ImportResultStep;
