import { useMemo, useState } from "react";
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
import GoalCard from "./goals/GoalCard.jsx";
import GoalForm from "./goals/GoalForm.jsx";
import { useApi } from "../api/useApi.js";
import { useCurrentUser } from "../api/useCurrentUser.js";
import { useAccounts } from "../api/useAccounts.js";
import { useGoals } from "../api/useGoals.js";
import { createAccount } from "../api/accounts.js";
import { createGoal } from "../api/goals.js";
import { useGoalAchievementSync } from "./goals/goalFinancials.js";
import { getSessionGreeting } from "../utils/greeting.js";
import DashboardSkeleton, { DashboardGreetingSkeleton } from "./DashboardSkeleton.jsx";
import "./goals/Goals.css";

/** How many active goals the dashboard widget shows before "See all" is
 * the only way to see the rest — keeps the widget to a glance-able size
 * regardless of MAX_GOALS. */
const DASHBOARD_GOALS_LIMIT = 4;

/**
 * The landing page once signed in (App.jsx redirects "/" and unknown
 * paths here — see DashboardPage's routing in App.jsx). An accounts
 * overview: every account as a card (see AccountCard.jsx), or a prompt to
 * create one when there aren't any yet. This page is otherwise read-only —
 * clicking any card (or "View all accounts") routes to the Accounts table,
 * which owns viewing/editing/deleting a specific account — but the empty state's
 * "Create an account" opens the same drawer AccountsListPage uses right
 * here, instead of a redirect + a second button click over there.
 * DashboardSkeleton fills the grid's place, and DashboardGreetingSkeleton
 * the greeting's, while useAccounts() is loading.
 *
 * Below the accounts grid, a Goals widget (see GoalCard.jsx) shows every
 * `active` goal as a card with its live client-side progress (see
 * goals/goalFinancials.js) — achieved goals drop out of this view, visible
 * only via the "See all" link through to GoalsListPage.
 */
function DashboardPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { user } = useAuth0();
  const { profile } = useCurrentUser();
  const { accounts, isLoading, error: loadError, setAccounts } = useAccounts();
  const { goals, isLoading: isGoalsLoading, setGoals } = useGoals();
  const activeGoals = goals.filter((goal) => goal.status === "active");

  useGoalAchievementSync(goals, accounts, api, setGoals);

  const [isGoalCreateOpen, setIsGoalCreateOpen] = useState(false);
  const [isGoalSaving, setIsGoalSaving] = useState(false);
  const [goalSaveError, setGoalSaveError] = useState(null);

  const closeGoalCreate = () => {
    setIsGoalCreateOpen(false);
    setGoalSaveError(null);
  };

  const handleGoalCreate = (values) => {
    setIsGoalSaving(true);
    setGoalSaveError(null);
    createGoal(api, values)
      .then((goal) => {
        setGoals((current) => [...current, goal]);
        closeGoalCreate();
      })
      .catch((err) => setGoalSaveError(err.message ?? "Couldn't create the goal."))
      .finally(() => setIsGoalSaving(false));
  };

  // Pinned to sessionStorage (see getSessionGreeting) so it stays the same
  // for the whole tab session, not just this mount.
  const greeting = useMemo(() => getSessionGreeting(user), [user]);

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
          defaultCurrency={profile?.default_currency}
          onSubmit={handleCreate}
          onCancel={closeCreate}
          isSubmitting={isSaving}
          error={saveError}
        />
      </Drawer>

      {!isGoalsLoading && (
        <>
          <div className="ec-section-head">
            <h2 className="ec-section-title">Goals</h2>
            {goals.length > 0 && (
              <Button variant="secondary" onClick={() => navigate("/goals")}>
                See all
              </Button>
            )}
          </div>

          {activeGoals.length === 0 && (
            <EmptyState
              title="No active goals"
              description="Set a goal and map accounts or pies to it to track progress toward it."
              action={
                <Button variant="primary" onClick={() => setIsGoalCreateOpen(true)}>
                  Set a goal
                </Button>
              }
            />
          )}

          {activeGoals.length > 0 && (
            <div className="ec-account-grid">
              {activeGoals.slice(0, DASHBOARD_GOALS_LIMIT).map((goal) => (
                <GoalCard
                  key={goal.id}
                  goal={goal}
                  accounts={accounts}
                  defaultCurrency={profile?.default_currency}
                  onClick={() => navigate("/goals")}
                />
              ))}
            </div>
          )}
        </>
      )}

      <Drawer open={isGoalCreateOpen} onClose={closeGoalCreate} title="New goal">
        <GoalForm
          accounts={accounts}
          claimedAccountIds={new Set(goals.flatMap((goal) => goal.account_ids ?? []))}
          claimedPieIds={new Set(goals.flatMap((goal) => goal.pie_ids ?? []))}
          onSubmit={handleGoalCreate}
          onCancel={closeGoalCreate}
          isSubmitting={isGoalSaving}
          error={goalSaveError}
        />
      </Drawer>
    </AppShell>
  );
}

export default DashboardPage;
