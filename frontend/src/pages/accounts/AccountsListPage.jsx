import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import Button from "../../components/core/Button.jsx";
import Badge from "../../components/core/Badge.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import AccountForm from "./AccountForm.jsx";
import { useApi } from "../../api/useApi.js";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import { useAccounts } from "../../api/useAccounts.js";
import { createAccount, deleteAccount, updateAccount } from "../../api/accounts.js";
import { MENU_ITEMS } from "../menuItems.js";

/** True once an account has pies/holdings that a plain delete would refuse (see accounts/views.py). */
function needsForce(account) {
  return (account.pies?.length ?? 0) > 0 || (account.holdings?.length ?? 0) > 0;
}

/**
 * The accounts management page: a table (not the card grid — DashboardPage
 * keeps that for its at-a-glance overview, see AccountCard.jsx) with an
 * add/edit/delete icon action per row, each backed by a side Drawer rather
 * than a centered Modal. A row click still routes to AccountDetailPage
 * (pies/holdings), unrelated to the row's own edit/delete icons.
 */
function AccountsListPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { profile } = useCurrentUser();
  const { accounts, isLoading, error: loadError, setAccounts } = useAccounts();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [editingAccount, setEditingAccount] = useState(null);
  const [isEditSaving, setIsEditSaving] = useState(false);
  const [editSaveError, setEditSaveError] = useState(null);

  const [deletingAccount, setDeletingAccount] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const closeCreate = () => {
    setIsCreateOpen(false);
    setSaveError(null);
  };

  const handleCreate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    createAccount(api, values)
      .then((account) => {
        setAccounts((current) => [...current, account]);
        closeCreate();
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't create the account."))
      .finally(() => setIsSaving(false));
  };

  const closeEdit = () => {
    setEditingAccount(null);
    setEditSaveError(null);
  };

  const handleEdit = (values) => {
    setIsEditSaving(true);
    setEditSaveError(null);
    updateAccount(api, editingAccount.id, values)
      .then((updated) => {
        setAccounts((current) =>
          current.map((account) => (account.id === updated.id ? { ...account, ...updated } : account))
        );
        closeEdit();
      })
      .catch((err) => setEditSaveError(err.message ?? "Couldn't update the account."))
      .finally(() => setIsEditSaving(false));
  };

  const closeDelete = () => {
    setDeletingAccount(null);
    setDeleteError(null);
  };

  const handleDelete = () => {
    setIsDeleting(true);
    setDeleteError(null);
    deleteAccount(api, deletingAccount.id, { force: needsForce(deletingAccount) })
      .then(() => {
        setAccounts((current) => current.filter((account) => account.id !== deletingAccount.id));
        closeDelete();
      })
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete the account."))
      .finally(() => setIsDeleting(false));
  };

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Portfolio"
      title="Accounts"
      subtitle="Every account you're tracking, with its pies and holdings nested underneath."
      actions={
        (isLoading || accounts.length > 0) && (
          <Button variant="primary" onClick={() => setIsCreateOpen(true)}>
            <i className="bi bi-plus-lg" aria-hidden="true" />
            New account
          </Button>
        )
      }
    >
      {isLoading && <p className="ec-loading">Loading…</p>}
      {loadError && <Alert tone="danger">{loadError}</Alert>}

      {!isLoading && !loadError && accounts.length === 0 && (
        <EmptyState
          title="No accounts yet"
          description="Create an account to start tracking pies and holdings against it."
          action={
            <Button variant="primary" onClick={() => setIsCreateOpen(true)}>
              New account
            </Button>
          }
        />
      )}

      {!isLoading && !loadError && accounts.length > 0 && (
        <div className="ec-table-wrap">
          <table className="ec-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Currency</th>
                <th>Transaction type</th>
                <th>Pies</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id} onClick={() => navigate(`/accounts/${account.id}`)}>
                  <td>
                    <div className="ec-table-name">{account.name}</div>
                    <div className="ec-table-desc">{account.description}</div>
                  </td>
                  <td>
                    <Badge tone="accent">{account.account_type}</Badge>
                  </td>
                  <td>{account.currency}</td>
                  <td>
                    <Badge tone={account.transaction_type === "TRANSACTION" ? "purple" : "info"}>
                      {account.transaction_type === "TRANSACTION" ? "Per-transaction" : "Average cost"}
                    </Badge>
                  </td>
                  <td>{(account.pies ?? []).length}</td>
                  <td>
                    <div className="ec-table-actions">
                      <button
                        type="button"
                        className="ec-icon-btn"
                        aria-label={`Edit ${account.name}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          setEditingAccount(account);
                        }}
                      >
                        <i className="bi bi-pencil" aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="ec-icon-btn ec-icon-btn--danger"
                        aria-label={`Delete ${account.name}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          setDeletingAccount(account);
                        }}
                      >
                        <i className="bi bi-trash" aria-hidden="true" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Drawer open={isCreateOpen} onClose={closeCreate} title="New account">
        <AccountForm
          defaultCurrency={profile?.default_currency}
          onSubmit={handleCreate}
          onCancel={closeCreate}
          isSubmitting={isSaving}
          error={saveError}
        />
      </Drawer>

      <Drawer open={Boolean(editingAccount)} onClose={closeEdit} title="Edit account">
        {editingAccount && (
          <AccountForm
            initialValues={editingAccount}
            onSubmit={handleEdit}
            onCancel={closeEdit}
            isSubmitting={isEditSaving}
            error={editSaveError}
          />
        )}
      </Drawer>

      <ConfirmDialog
        open={Boolean(deletingAccount)}
        title="Delete account"
        message={
          deletingAccount && needsForce(deletingAccount)
            ? "This account still has pies and/or holdings. Deleting it will also delete all of them, along with any recorded transactions. This can't be undone."
            : "This will permanently delete the account. This can't be undone."
        }
        confirmLabel="Delete account"
        isLoading={isDeleting}
        onConfirm={handleDelete}
        onCancel={closeDelete}
      />
      {deleteError && (
        <div className="ec-detail-delete-error">
          <Alert tone="danger">{deleteError}</Alert>
        </div>
      )}
    </AppShell>
  );
}

export default AccountsListPage;
