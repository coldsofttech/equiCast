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
import { hasWarmedFxRates, warmFxRates } from "../utils/fxWarmup.js";
import { getSessionGreeting } from "../utils/greeting.js";
import AppLoadingScreen from "./AppLoadingScreen.jsx";
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
 * Also the trigger point for the login-time FX warm-up (GitHub issues
 * #149/#177, see utils/fxWarmup.js) — this is the first page every
 * signed-in user lands on. While that warm-up is still in flight (a
 * genuine first load this tab session only — see hasWarmedFxRates), the
 * whole page is replaced by AppLoadingScreen, a fancier "getting
 * everything ready" overlay, rather than rendering AppShell around a
 * part-loaded page. It resolves once and never shows again this session,
 * regardless of what accounts/profile do afterward.
 *
 * DashboardSkeleton fills the grid's place, and DashboardGreetingSkeleton
 * the greeting's, while useAccounts() is loading — including a later
 * same-session remount, where AppLoadingScreen itself is skipped (FX
 * warm-up already settled) but accounts may still be genuinely refetching.
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
  const { profile, error: profileError } = useCurrentUser();
  const { accounts, isLoading, error: loadError, errorStatus, setAccounts } = useAccounts();

  // Pinned to sessionStorage (see getSessionGreeting) so it stays the same
  // for the whole tab session, not just this mount.
  const greeting = useMemo(() => getSessionGreeting(user), [user]);

  // Lazily seeded from hasWarmedFxRates() rather than a plain `true`, so a
  // same-session remount (warm-up already done, nothing pending) doesn't
  // flash AppLoadingScreen for a frame before this effect gets a chance to
  // resolve it — only a genuine first-load-this-session starts `true`.
  const [isWarmingFx, setIsWarmingFx] = useState(() => !hasWarmedFxRates());

  useEffect(() => {
    // A failed profile fetch has nothing to warm up with — don't leave
    // AppLoadingScreen showing forever waiting on a `profile` that's never
    // going to arrive; loadError's own ServiceUnavailablePage check below
    // takes over from here instead.
    if (profileError) {
      setIsWarmingFx(false);
      return;
    }
    if (!profile) return;
    let cancelled = false;
    warmFxRates(api, profile).then(() => {
      if (!cancelled) setIsWarmingFx(false);
    });
    return () => {
      cancelled = true;
    };
  }, [api, profile, profileError]);

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

  if (isWarmingFx) {
    return <AppLoadingScreen />;
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
