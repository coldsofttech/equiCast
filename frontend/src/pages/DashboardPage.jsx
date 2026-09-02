import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/shell/AppShell.jsx";
import SiteFooter from "../components/shell/SiteFooter.jsx";
import Button from "../components/core/Button.jsx";
import Alert from "../components/core/Alert.jsx";
import EmptyState from "../components/core/EmptyState.jsx";
import Drawer from "../components/core/Drawer.jsx";
import AccountCard from "./accounts/AccountCard.jsx";
import AccountForm from "./accounts/AccountForm.jsx";
import { useApi } from "../api/useApi.js";
import { useCurrentUser } from "../api/useCurrentUser.js";
import { useAccounts } from "../api/useAccounts.js";
import { createAccount } from "../api/accounts.js";
import { MENU_ITEMS } from "./menuItems.js";

/**
 * The landing page once signed in (App.jsx redirects "/" and unknown
 * paths here — see DashboardPage's routing in App.jsx). An accounts
 * overview: every account as a card (AccountsListPage's own card, reused
 * via AccountCard so the two don't diverge), or a prompt to create one
 * when there aren't any yet. This page is otherwise read-only — clicking
 * any card (or "View all accounts") routes to the Accounts table, which
 * owns viewing/editing/deleting a specific account — but the empty state's
 * "Create an account" opens the same drawer AccountsListPage uses right
 * here, instead of a redirect + a second button click over there.
 */
function DashboardPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { profile } = useCurrentUser();
  const { accounts, isLoading, error: loadError, setAccounts } = useAccounts();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

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

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Overview"
      title="Dashboard"
      subtitle="Every account you're tracking, at a glance."
      actions={
        accounts.length > 0 && (
          <Button variant="primary" onClick={() => navigate("/accounts")}>
            View all accounts
          </Button>
        )
      }
      footer={<SiteFooter />}
    >
      {isLoading && <p className="ec-loading">Loading…</p>}
      {loadError && <Alert tone="danger">{loadError}</Alert>}

      {!isLoading && !loadError && accounts.length === 0 && (
        <EmptyState
          title="No accounts yet"
          description="Create an account to start tracking pies and holdings against it."
          action={
            <Button variant="primary" onClick={() => setIsCreateOpen(true)}>
              Create an account
            </Button>
          }
        />
      )}

      {!isLoading && !loadError && accounts.length > 0 && (
        <div className="ec-account-grid">
          {accounts.map((account) => (
            <AccountCard key={account.id} account={account} onClick={() => navigate("/accounts")} />
          ))}
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
    </AppShell>
  );
}

export default DashboardPage;
