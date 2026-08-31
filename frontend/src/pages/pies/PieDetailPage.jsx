import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import Card from "../../components/core/Card.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import Modal from "../../components/core/Modal.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import PieForm from "./PieForm.jsx";
import AllocationEditor from "./AllocationEditor.jsx";
import { useApi } from "../../api/useApi.js";
import { deletePie, getPie, syncPieHoldings, updatePie } from "../../api/pies.js";
import { MENU_ITEMS } from "../menuItems.js";

function PieDetailPage() {
  const { accountId, pieId } = useParams();
  const api = useApi();
  const navigate = useNavigate();

  const [pie, setPie] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const [isAllocationSaving, setIsAllocationSaving] = useState(false);
  const [allocationError, setAllocationError] = useState(null);

  useEffect(() => {
    setIsLoading(true);
    setLoadError(null);
    getPie(api, pieId)
      .then(setPie)
      .catch((err) => setLoadError(err.message ?? "Couldn't load this pie."))
      .finally(() => setIsLoading(false));
  }, [api, pieId]);

  const handleUpdate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    updatePie(api, pieId, values)
      .then((updated) => {
        setPie((current) => ({ ...current, ...updated }));
        setIsEditOpen(false);
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't update the pie."))
      .finally(() => setIsSaving(false));
  };

  const handleDelete = () => {
    setIsDeleting(true);
    setDeleteError(null);
    deletePie(api, pieId, { force: (pie.holdings?.length ?? 0) > 0 })
      .then(() => navigate(`/accounts/${accountId}`))
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete the pie."))
      .finally(() => setIsDeleting(false));
  };

  const handleSaveAllocation = (batch) => {
    setIsAllocationSaving(true);
    setAllocationError(null);
    syncPieHoldings(api, pieId, batch)
      .then((updated) => setPie(updated))
      .catch((err) => setAllocationError(err.message ?? "Couldn't save the allocation changes."))
      .finally(() => setIsAllocationSaving(false));
  };

  if (isLoading) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Loading…">
        <p className="ec-loading">Loading…</p>
      </AppShell>
    );
  }

  if (loadError || !pie) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Pie">
        <Alert tone="danger">{loadError ?? "Pie not found."}</Alert>
      </AppShell>
    );
  }

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Portfolio"
      title={pie.name}
      subtitle={pie.description}
      actions={
        <>
          <Button variant="ghost" onClick={() => navigate(`/accounts/${accountId}`)}>
            Back to account
          </Button>
          <Button variant="secondary" onClick={() => setIsEditOpen(true)}>
            Edit
          </Button>
          <Button variant="danger" onClick={() => setIsDeleteOpen(true)}>
            Delete
          </Button>
        </>
      }
    >
      <Card>
        <AllocationEditor
          holdings={pie.holdings ?? []}
          onSave={handleSaveAllocation}
          isSaving={isAllocationSaving}
          error={allocationError}
        />
      </Card>

      <Modal
        open={isEditOpen}
        onClose={() => {
          setIsEditOpen(false);
          setSaveError(null);
        }}
        title="Edit pie"
      >
        <PieForm
          initialValues={pie}
          onSubmit={handleUpdate}
          onCancel={() => {
            setIsEditOpen(false);
            setSaveError(null);
          }}
          isSubmitting={isSaving}
          error={saveError}
        />
      </Modal>

      <ConfirmDialog
        open={isDeleteOpen}
        title="Delete pie"
        message={
          (pie.holdings?.length ?? 0) > 0
            ? "This pie still has holdings. Deleting it will also delete them, along with any recorded transactions. This can't be undone."
            : "This will permanently delete the pie. This can't be undone."
        }
        confirmLabel="Delete pie"
        isLoading={isDeleting}
        onConfirm={handleDelete}
        onCancel={() => {
          setIsDeleteOpen(false);
          setDeleteError(null);
        }}
      />
      {deleteError && (
        <div className="ec-detail-delete-error">
          <Alert tone="danger">{deleteError}</Alert>
        </div>
      )}
    </AppShell>
  );
}

export default PieDetailPage;
