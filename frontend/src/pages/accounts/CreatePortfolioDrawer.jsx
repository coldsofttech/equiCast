import { useState } from "react";
import Drawer from "../../components/core/Drawer.jsx";
import AllocationEditor from "../pies/AllocationEditor.jsx";
import PieForm from "../pies/PieForm.jsx";
import { useApi } from "../../api/useApi.js";
import { createPie, syncPieHoldings } from "../../api/pies.js";

/**
 * Two-step "New portfolio" drawer, opened from AccountDetailPage just
 * before the Portfolios list. Step 1 creates the pie (name/description —
 * PieForm, the same form PieDetailPage uses to edit one); step 2 shows the
 * same AllocationEditor PieDetailPage uses, so a caller can search/add
 * holdings and set allocations right away, without leaving the drawer.
 * Closing after step 1 still leaves a real (empty) pie behind — that's the
 * same as creating one with no holdings via any other path, not an error
 * state, so there's no separate "cancel the whole thing" affordance once
 * the pie exists.
 */
function CreatePortfolioDrawer({ open, accountId, onClose, onCreated, onHoldingsSaved }) {
  const api = useApi();
  const [pie, setPie] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [isAllocationSaving, setIsAllocationSaving] = useState(false);
  const [allocationError, setAllocationError] = useState(null);

  const handleClose = () => {
    onClose();
    setPie(null);
    setSaveError(null);
    setAllocationError(null);
  };

  const handleCreate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    createPie(api, { ...values, account_id: accountId })
      .then((created) => {
        setPie(created);
        onCreated(created);
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't create the portfolio."))
      .finally(() => setIsSaving(false));
  };

  const handleSaveAllocation = (batch) => {
    setIsAllocationSaving(true);
    setAllocationError(null);
    syncPieHoldings(api, pie.id, batch)
      .then((updated) => {
        setPie(updated);
        onHoldingsSaved(updated);
      })
      .catch((err) => setAllocationError(err.message ?? "Couldn't save the allocation changes."))
      .finally(() => setIsAllocationSaving(false));
  };

  return (
    <Drawer
      open={open}
      onClose={handleClose}
      title={pie ? `Add holdings to ${pie.name}` : "New portfolio"}
    >
      {pie ? (
        <AllocationEditor
          holdings={pie.holdings ?? []}
          onSave={handleSaveAllocation}
          isSaving={isAllocationSaving}
          error={allocationError}
        />
      ) : (
        <PieForm
          onSubmit={handleCreate}
          onCancel={handleClose}
          isSubmitting={isSaving}
          error={saveError}
        />
      )}
    </Drawer>
  );
}

export default CreatePortfolioDrawer;
