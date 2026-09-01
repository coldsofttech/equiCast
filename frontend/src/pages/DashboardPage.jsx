import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "../components/shell/AppShell.jsx";
import SiteFooter from "../components/shell/SiteFooter.jsx";
import Button from "../components/core/Button.jsx";
import Alert from "../components/core/Alert.jsx";
import EmptyState from "../components/core/EmptyState.jsx";
import AccountCard from "./accounts/AccountCard.jsx";
import { useApi } from "../api/useApi.js";
import { listAccounts } from "../api/accounts.js";
import { MENU_ITEMS } from "./menuItems.js";

/**
 * The landing page once signed in (App.jsx redirects "/" and unknown
 * paths here — see DashboardPage's routing in App.jsx). An accounts
 * overview: every account as a card (AccountsListPage's own card, reused
 * via AccountCard so the two don't diverge), or a prompt to create one
 * when there aren't any yet. This page is read-only — clicking any card
 * (or "View all accounts") routes to the Accounts table, which owns
 * viewing/creating/editing/deleting a specific account.
 */
function DashboardPage() {
  const api = useApi();
  const navigate = useNavigate();

  const [accounts, setAccounts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

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
            <Button variant="primary" onClick={() => navigate("/accounts")}>
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
    </AppShell>
  );
}

export default DashboardPage;
