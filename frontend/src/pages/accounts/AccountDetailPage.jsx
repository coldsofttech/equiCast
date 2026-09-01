import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Modal from "../../components/core/Modal.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import AccountForm from "./AccountForm.jsx";
import PieForm from "../pies/PieForm.jsx";
import { useApi } from "../../api/useApi.js";
import { deleteAccount, getAccount, updateAccount } from "../../api/accounts.js";
import { createPie, deletePie } from "../../api/pies.js";
import { MENU_ITEMS } from "../menuItems.js";
import "./AccountDetailPage.css";

function AccountDetailPage() {
  const { accountId } = useParams();
  const api = useApi();
  const navigate = useNavigate();

  const [account, setAccount] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const [isPieModalOpen, setIsPieModalOpen] = useState(false);
  const [isPieSaving, setIsPieSaving] = useState(false);
  const [pieSaveError, setPieSaveError] = useState(null);

  const [deletingPieId, setDeletingPieId] = useState(null);
  const [pieDeleteError, setPieDeleteError] = useState(null);

  const load = () => {
    setIsLoading(true);
    setLoadError(null);
    getAccount(api, accountId)
      .then(setAccount)
      .catch((err) => setLoadError(err.message ?? "Couldn't load this account."))
      .finally(() => setIsLoading(false));
  };

  useEffect(load, [api, accountId]);

  const handleUpdate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    updateAccount(api, accountId, values)
      .then((updated) => {
        setAccount((current) => ({ ...current, ...updated }));
        setIsEditOpen(false);
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't update the account."))
      .finally(() => setIsSaving(false));
  };

  const needsForce = account && ((account.pies?.length ?? 0) > 0 || (account.holdings?.length ?? 0) > 0);

  const handleDelete = () => {
    setIsDeleting(true);
    setDeleteError(null);
    deleteAccount(api, accountId, { force: needsForce })
      .then(() => navigate("/accounts"))
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete the account."))
      .finally(() => setIsDeleting(false));
  };

  const handleCreatePie = (values) => {
    setIsPieSaving(true);
    setPieSaveError(null);
    createPie(api, { ...values, account_id: accountId })
      .then((pie) => {
        setAccount((current) => ({ ...current, pies: [...(current.pies ?? []), pie] }));
        setIsPieModalOpen(false);
      })
      .catch((err) => setPieSaveError(err.message ?? "Couldn't create the pie."))
      .finally(() => setIsPieSaving(false));
  };

  const handleDeletePie = (pie) => {
    setPieDeleteError(null);
    deletePie(api, pie.id, { force: (pie.holdings?.length ?? 0) > 0 })
      .then(() => {
        setAccount((current) => ({
          ...current,
          pies: current.pies.filter((p) => p.id !== pie.id),
        }));
        setDeletingPieId(null);
      })
      .catch((err) => setPieDeleteError(err.message ?? "Couldn't delete the pie."));
  };

  if (isLoading) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Loading…">
        <p className="ec-loading">Loading…</p>
      </AppShell>
    );
  }

  if (loadError || !account) {
    return (
      <AppShell menuItems={MENU_ITEMS} eyebrow="Portfolio" title="Account">
        <Alert tone="danger">{loadError ?? "Account not found."}</Alert>
      </AppShell>
    );
  }

  const pieBeingDeleted = account.pies?.find((p) => p.id === deletingPieId);

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Portfolio"
      title={account.name}
      subtitle={account.description}
      actions={
        <>
          <Button variant="secondary" onClick={() => setIsEditOpen(true)}>
            Edit
          </Button>
          <Button variant="danger" onClick={() => setIsDeleteOpen(true)}>
            Delete
          </Button>
        </>
      }
    >
      <div className="ec-account-detail-badges">
        <Badge tone="accent">{account.account_type}</Badge>
        <Badge tone="neutral">{account.currency}</Badge>
        <Badge tone={account.transaction_type === "TRANSACTION" ? "purple" : "info"}>
          {account.transaction_type === "TRANSACTION" ? "Per-transaction" : "Average cost"}
        </Badge>
      </div>

      <div className="ec-section-head">
        <h2 className="ec-section-title">Pies</h2>
        <Button variant="primary" size="sm" onClick={() => setIsPieModalOpen(true)}>
          New pie
        </Button>
      </div>

      {pieDeleteError && <Alert tone="danger">{pieDeleteError}</Alert>}

      {(account.pies ?? []).length === 0 ? (
        <EmptyState
          title="No pies yet"
          description="A pie holds a 100%-allocated slice of this account across one or more tickers."
          action={
            <Button variant="primary" onClick={() => setIsPieModalOpen(true)}>
              New pie
            </Button>
          }
        />
      ) : (
        <div className="ec-account-grid">
          {account.pies.map((pie) => (
            <Card
              key={pie.id}
              className="ec-account-card"
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/accounts/${accountId}/pies/${pie.id}`)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  navigate(`/accounts/${accountId}/pies/${pie.id}`);
                }
              }}
            >
              <div className="ec-account-card-head">
                <h3 className="ec-account-card-name">{pie.name}</h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(event) => {
                    event.stopPropagation();
                    setDeletingPieId(pie.id);
                  }}
                >
                  Delete
                </Button>
              </div>
              <p className="ec-account-card-desc">{pie.description}</p>
              <span className="ec-account-card-count">{(pie.holdings ?? []).length} holdings</span>
            </Card>
          ))}
        </div>
      )}

      <Drawer
        open={isEditOpen}
        onClose={() => {
          setIsEditOpen(false);
          setSaveError(null);
        }}
        title="Edit account"
      >
        <AccountForm
          initialValues={account}
          onSubmit={handleUpdate}
          onCancel={() => {
            setIsEditOpen(false);
            setSaveError(null);
          }}
          isSubmitting={isSaving}
          error={saveError}
        />
      </Drawer>

      <Modal
        open={isPieModalOpen}
        onClose={() => {
          setIsPieModalOpen(false);
          setPieSaveError(null);
        }}
        title="New pie"
      >
        <PieForm
          onSubmit={handleCreatePie}
          onCancel={() => {
            setIsPieModalOpen(false);
            setPieSaveError(null);
          }}
          isSubmitting={isPieSaving}
          error={pieSaveError}
        />
      </Modal>

      <ConfirmDialog
        open={isDeleteOpen}
        title="Delete account"
        message={
          needsForce
            ? "This account still has pies and/or holdings. Deleting it will also delete all of them, along with any recorded transactions. This can't be undone."
            : "This will permanently delete the account. This can't be undone."
        }
        confirmLabel="Delete account"
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

      <ConfirmDialog
        open={Boolean(deletingPieId)}
        title="Delete pie"
        message={
          pieBeingDeleted && (pieBeingDeleted.holdings?.length ?? 0) > 0
            ? "This pie still has holdings. Deleting it will also delete them, along with any recorded transactions. This can't be undone."
            : "This will permanently delete the pie. This can't be undone."
        }
        confirmLabel="Delete pie"
        onConfirm={() => pieBeingDeleted && handleDeletePie(pieBeingDeleted)}
        onCancel={() => setDeletingPieId(null)}
      />
    </AppShell>
  );
}

export default AccountDetailPage;
