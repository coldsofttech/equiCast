import { useState } from "react";
import Drawer from "../../components/core/Drawer.jsx";
import PieForm from "../pies/PieForm.jsx";
import { useApi } from "../../api/useApi.js";
import { createPie } from "../../api/pies.js";

/**
 * "New portfolio" drawer, opened from AccountDetailPage just before the
 * Portfolios list — just the pie's name/description (PieForm, the same
 * form PieDetailPage uses to edit one). Holdings aren't set here: once the
 * pie exists, its own detail page's Edit action is where allocations get
 * added, same as any other pie.
 */
function CreatePortfolioDrawer({ open, accountId, onClose, onCreated }) {
  const api = useApi();
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const handleClose = () => {
    onClose();
    setSaveError(null);
  };

  const handleCreate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    createPie(api, { ...values, account_id: accountId })
      .then((created) => {
        onCreated(created);
        handleClose();
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't create the portfolio."))
      .finally(() => setIsSaving(false));
  };

  return (
    <Drawer open={open} onClose={handleClose} title="New portfolio">
      <PieForm
        onSubmit={handleCreate}
        onCancel={handleClose}
        isSubmitting={isSaving}
        error={saveError}
      />
    </Drawer>
  );
}

export default CreatePortfolioDrawer;
