import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import { useApi } from "../../api/useApi.js";
import { listAccounts } from "../../api/accounts.js";
import ImportUploadStep from "./ImportUploadStep.jsx";
import ImportReviewStep from "./ImportReviewStep.jsx";
import ImportResultStep from "./ImportResultStep.jsx";

/**
 * Dedicated "Import transactions" page (Account menu → Import
 * transactions) — not scoped to any one account/pie up front, since the
 * user maps each imported holding to a target during review. Three steps,
 * swapped in place rather than routed separately (nothing here needs to be
 * a bookmarkable/back-button-able sub-URL of its own): upload (parse via
 * ImportPreviewView), review (map/select via TickerSearchField and an
 * account/pie picker, then ImportCommitView), result. See
 * docs/importing-transactions.md for the user-facing file-format
 * reference this whole flow implements.
 */
function ImportPage() {
  const api = useApi();
  const navigate = useNavigate();
  const [step, setStep] = useState("upload");
  const [preview, setPreview] = useState(null);
  const [results, setResults] = useState(null);
  const [accounts, setAccounts] = useState([]);

  useEffect(() => {
    listAccounts(api)
      .then(setAccounts)
      .catch(() => setAccounts([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AppShell
      eyebrow="Portfolio"
      title="Import transactions"
      subtitle="Upload a CSV or Trading 212 export, review what was parsed, then import."
      footer={<SiteFooter />}
    >
      {step === "upload" && (
        <ImportUploadStep
          onParsed={(parsedPreview) => {
            setPreview(parsedPreview);
            setStep("review");
          }}
          onCancel={() => navigate(-1)}
        />
      )}
      {step === "review" && preview && (
        <ImportReviewStep
          preview={preview}
          accounts={accounts}
          onBack={() => setStep("upload")}
          onCommitted={(commitResults) => {
            setResults(commitResults);
            setStep("result");
          }}
          onCancel={() => navigate(-1)}
        />
      )}
      {step === "result" && results && (
        <ImportResultStep results={results} onDone={() => navigate("/accounts")} />
      )}
    </AppShell>
  );
}

export default ImportPage;
