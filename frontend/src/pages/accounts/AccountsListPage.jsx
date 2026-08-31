import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Modal from "../../components/core/Modal.jsx";
import AccountForm from "./AccountForm.jsx";
import { useApi } from "../../api/useApi.js";
import { createAccount, listAccounts } from "../../api/accounts.js";
import { MENU_ITEMS } from "../menuItems.js";

function AccountsListPage() {
  const api = useApi();
  const navigate = useNavigate();

  const [accounts, setAccounts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setLoadError(null);
    listAccounts(api)
      .then((result) => {
        if (!cancelled) setAccounts(result);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message ?? "Couldn't load your accounts.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api]);

  const handleCreate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    createAccount(api, values)
      .then((account) => {
        setAccounts((current) => [...current, account]);
        setIsModalOpen(false);
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't create the account."))
      .finally(() => setIsSaving(false));
  };

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Portfolio"
      title="Accounts"
      subtitle="Every account you're tracking, with its pies and holdings nested underneath."
      actions={
        <Button variant="primary" onClick={() => setIsModalOpen(true)}>
          New account
        </Button>
      }
    >
      {isLoading && <p className="ec-loading">Loading…</p>}
      {loadError && <Alert tone="danger">{loadError}</Alert>}

      {!isLoading && !loadError && accounts.length === 0 && (
        <EmptyState
          title="No accounts yet"
          description="Create an account to start tracking pies and holdings against it."
          action={
            <Button variant="primary" onClick={() => setIsModalOpen(true)}>
              New account
            </Button>
          }
        />
      )}

      {!isLoading && !loadError && accounts.length > 0 && (
        <div className="ec-account-grid">
          {accounts.map((account) => (
            <Card
              key={account.id}
              className="ec-account-card"
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/accounts/${account.id}`)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  navigate(`/accounts/${account.id}`);
                }
              }}
            >
              <div className="ec-account-card-head">
                <h2 className="ec-account-card-name">{account.name}</h2>
                <Badge tone="accent">{account.account_type}</Badge>
              </div>
              <p className="ec-account-card-desc">{account.description}</p>
              <div className="ec-account-card-meta">
                <Badge tone="neutral">{account.currency}</Badge>
                <Badge tone={account.transaction_type === "TRANSACTION" ? "purple" : "info"}>
                  {account.transaction_type === "TRANSACTION" ? "Per-transaction" : "Average cost"}
                </Badge>
                <span className="ec-account-card-count">{(account.pies ?? []).length} pies</span>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setSaveError(null);
        }}
        title="New account"
      >
        <AccountForm
          onSubmit={handleCreate}
          onCancel={() => {
            setIsModalOpen(false);
            setSaveError(null);
          }}
          isSubmitting={isSaving}
          error={saveError}
        />
      </Modal>
    </AppShell>
  );
}

export default AccountsListPage;
