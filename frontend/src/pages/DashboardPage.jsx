import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import AppShell from "../components/shell/AppShell.jsx";
import SiteFooter from "../components/shell/SiteFooter.jsx";
import Button from "../components/core/Button.jsx";
import Alert from "../components/core/Alert.jsx";
import EmptyState from "../components/core/EmptyState.jsx";
import Drawer from "../components/core/Drawer.jsx";
import AccountCard from "./accounts/AccountCard.jsx";
import AccountForm from "./accounts/AccountForm.jsx";
import ServiceUnavailablePage from "./errors/ServiceUnavailablePage.jsx";
import isServiceUnavailableError from "../components/errors/isServiceUnavailableError.js";
import { useApi } from "../api/useApi.js";
import { useCurrentUser } from "../api/useCurrentUser.js";
import { useAccounts } from "../api/useAccounts.js";
import { createAccount } from "../api/accounts.js";
import { warmFxRates } from "../utils/fxWarmup.js";
import { getSessionGreeting } from "../utils/greeting.js";
import DashboardSkeleton, { DashboardGreetingSkeleton } from "./DashboardSkeleton.jsx";

/**
 * The landing page once signed in (App.jsx redirects "/" here — see
 * DashboardPage's routing in App.jsx). An accounts overview: every
 * account as a card (see AccountCard.jsx), or a prompt to create one when
 * there aren't any yet. This page is otherwise read-only — clicking any
 * card (or "View all accounts") routes to the Accounts table, which owns
 * viewing/editing/deleting a specific account — but the empty state's
 * "Create an account" opens the same drawer AccountsListPage uses right
 * here, instead of a redirect + a second button click over there.
 *
 * Also the trigger point for the login-time FX warm-up (GitHub issue #149,
 * see utils/fxWarmup.js) — this is the first page every signed-in user
 * lands on, and by the time `profile` has loaded here the warm-up can run
 * silently in the background well before the user ever reaches a
 * transaction form.
 *
 * DashboardSkeleton fills the grid's place, and DashboardGreetingSkeleton
 * the greeting's, while useAccounts() is loading.
 *
 * A load failure severe enough to be a real outage (a network failure or
 * a 5xx, not an ordinary empty/validation state — see
 * isServiceUnavailableError.js) replaces the whole page with
 * ServiceUnavailablePage rather than rendering AppShell with an inline
 * Alert — this is the landing page, so there's nothing else useful to
 * show around that failure anyway.
 */
function DashboardPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { user } = useAuth0();
  const { profile } = useCurrentUser();
  const { accounts, isLoading, error: loadError, errorStatus, setAccounts } = useAccounts();

  // Pinned to sessionStorage (see getSessionGreeting) so it stays the same
  // for the whole tab session, not just this mount.
  const greeting = useMemo(() => getSessionGreeting(user), [user]);

  useEffect(() => {
    if (profile) warmFxRates(api, profile);
  }, [api, profile]);

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

  if (loadError && isServiceUnavailableError(errorStatus)) {
    return <ServiceUnavailablePage onRetry={() => window.location.reload()} />;
  }

  return (
    <AppShell
      greeting={
        isLoading ? (
          <DashboardGreetingSkeleton />
        ) : (
          <>
            <div className="ec-page-greeting-title">{greeting.title}</div>
            <div className="ec-page-greeting-subtitle">{greeting.subtitle}</div>
          </>
        )
      }
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
      {isLoading && <DashboardSkeleton />}
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
            <AccountCard
              key={account.id}
              account={account}
              defaultCurrency={profile?.default_currency}
              onClick={() => navigate(`/accounts/${account.id}`)}
            />
          ))}
        </div>
      )}

      <Drawer open={isCreateOpen} onClose={closeCreate} title="New account">
        <AccountForm
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
