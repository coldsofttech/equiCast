import { useMemo, useState } from "react";
import AppShell from "../../components/shell/AppShell.jsx";
import SiteFooter from "../../components/shell/SiteFooter.jsx";
import Button from "../../components/core/Button.jsx";
import Badge from "../../components/core/Badge.jsx";
import IconBadge from "../../components/core/IconBadge.jsx";
import Alert from "../../components/core/Alert.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import GoalProgressBar from "../../components/goals/GoalProgressBar.jsx";
import GoalForm from "./GoalForm.jsx";
import { computeGoalProgress, useGoalAchievementSync } from "./goalFinancials.js";
import { GOAL_PURPOSE_BADGE_TONES, GOAL_PURPOSE_ICONS, GOAL_PURPOSE_LABELS } from "../../config/goalPurposes.js";
import { formatCurrency } from "../sampleFinancials.js";
import { useApi } from "../../api/useApi.js";
import { useCurrentUser } from "../../api/useCurrentUser.js";
import { useAccounts } from "../../api/useAccounts.js";
import { useGoals } from "../../api/useGoals.js";
import { createGoal, deleteGoal, updateGoal } from "../../api/goals.js";
import "./Goals.css";

const FALLBACK_CURRENCY = "USD";

/** ids already mapped to a goal other than `excludeGoalId` — feeds
 * GoalForm's mapping picker so a claimed account/pie can't be double-
 * mapped (the backend also enforces this, see backend/goals/views.py, but
 * disabling it in the picker avoids a round-trip 409). */
function claimedIds(goals, excludeGoalId, field) {
  const ids = new Set();
  for (const goal of goals) {
    if (goal.id === excludeGoalId) continue;
    for (const id of goal[field] ?? []) ids.add(id);
  }
  return ids;
}

function purposeLabel(goal) {
  return goal.purpose === "other" ? goal.custom_purpose || "Other" : GOAL_PURPOSE_LABELS[goal.purpose];
}

/**
 * The goals management page: a table (same shape as AccountsListPage) with
 * add/edit/delete per row, each backed by a side Drawer/ConfirmDialog.
 * Goals have no nested children/detail page, so unlike accounts a row
 * click does nothing — edit/delete icons are the only row actions.
 *
 * Shows `active` goals by default; "See all" reveals `achieved` ones too
 * (they're hidden by default once achieved — see goalFinancials.js's
 * useGoalAchievementSync, which this page also runs so a goal crossing its
 * target while this page is open flips status immediately).
 */
function GoalsListPage() {
  const api = useApi();
  const { profile } = useCurrentUser();
  const { accounts } = useAccounts();
  const { goals, isLoading, error: loadError, setGoals } = useGoals();
  const defaultCurrency = profile?.default_currency ?? FALLBACK_CURRENCY;

  useGoalAchievementSync(goals, accounts, api, setGoals);

  const [showAll, setShowAll] = useState(false);
  const visibleGoals = useMemo(
    () => (showAll ? goals : goals.filter((goal) => goal.status === "active")),
    [goals, showAll]
  );

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [editingGoal, setEditingGoal] = useState(null);
  const [isEditSaving, setIsEditSaving] = useState(false);
  const [editSaveError, setEditSaveError] = useState(null);

  const [deletingGoal, setDeletingGoal] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);

  const closeCreate = () => {
    setIsCreateOpen(false);
    setSaveError(null);
  };

  const handleCreate = (values) => {
    setIsSaving(true);
    setSaveError(null);
    createGoal(api, values)
      .then((goal) => {
        setGoals((current) => [...current, goal]);
        closeCreate();
      })
      .catch((err) => setSaveError(err.message ?? "Couldn't create the goal."))
      .finally(() => setIsSaving(false));
  };

  const closeEdit = () => {
    setEditingGoal(null);
    setEditSaveError(null);
  };

  const handleEdit = (values) => {
    setIsEditSaving(true);
    setEditSaveError(null);
    updateGoal(api, editingGoal.id, values)
      .then((updated) => {
        setGoals((current) => current.map((goal) => (goal.id === updated.id ? updated : goal)));
        closeEdit();
      })
      .catch((err) => setEditSaveError(err.message ?? "Couldn't update the goal."))
      .finally(() => setIsEditSaving(false));
  };

  const closeDelete = () => {
    setDeletingGoal(null);
    setDeleteError(null);
  };

  const handleDelete = () => {
    setIsDeleting(true);
    setDeleteError(null);
    deleteGoal(api, deletingGoal.id)
      .then(() => {
        setGoals((current) => current.filter((goal) => goal.id !== deletingGoal.id));
        closeDelete();
      })
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete the goal."))
      .finally(() => setIsDeleting(false));
  };

  return (
    <AppShell
      eyebrow="Portfolio"
      title="Goals"
      subtitle="What you're saving for, and how close you are."
      footer={<SiteFooter />}
      actions={
        (isLoading || goals.length > 0) && (
          <Button variant="primary" onClick={() => setIsCreateOpen(true)}>
            <i className="bi bi-plus-lg" aria-hidden="true" />
            New goal
          </Button>
        )
      }
    >
      {isLoading && <p className="ec-loading">Loading…</p>}
      {loadError && <Alert tone="danger">{loadError}</Alert>}

      {!isLoading && !loadError && goals.length === 0 && (
        <EmptyState
          title="No goals yet"
          description="Set a goal and map accounts or pies to it to track progress toward it."
          action={
            <Button variant="primary" onClick={() => setIsCreateOpen(true)}>
              New goal
            </Button>
          }
        />
      )}

      {!isLoading && !loadError && goals.length > 0 && (
        <>
          <div className="ec-section-head">
            <span />
            <Button variant="secondary" onClick={() => setShowAll((v) => !v)}>
              {showAll ? "Show active only" : "See all"}
            </Button>
          </div>

          <div className="ec-table-wrap">
            <table className="ec-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Purpose</th>
                  <th>Progress</th>
                  <th>Target date</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {visibleGoals.map((goal) => {
                  const { currentValue, progressPct, isAchieved } = computeGoalProgress(goal, accounts);
                  return (
                    <tr key={goal.id}>
                      <td>
                        <div className="ec-table-name-cell">
                          <IconBadge icon={GOAL_PURPOSE_ICONS[goal.purpose]} defaultIcon="flag-fill" size={28} />
                          <div>
                            <div className="ec-table-name">{goal.name}</div>
                            <div className="ec-table-desc">
                              {formatCurrency(currentValue, defaultCurrency)} of{" "}
                              {formatCurrency(goal.target_amount, defaultCurrency)}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <Badge tone={goal.status === "achieved" ? "success" : GOAL_PURPOSE_BADGE_TONES[goal.purpose]}>
                          {goal.status === "achieved" ? "Achieved" : purposeLabel(goal)}
                        </Badge>
                      </td>
                      <td style={{ minWidth: 140 }}>
                        <GoalProgressBar pct={progressPct} achieved={isAchieved} />
                      </td>
                      <td>{goal.target_date ?? "—"}</td>
                      <td>
                        <div className="ec-table-actions">
                          <button
                            type="button"
                            className="ec-icon-btn"
                            aria-label={`Edit ${goal.name}`}
                            onClick={() => setEditingGoal(goal)}
                          >
                            <i className="bi bi-pencil" aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            className="ec-icon-btn ec-icon-btn--danger"
                            aria-label={`Delete ${goal.name}`}
                            onClick={() => setDeletingGoal(goal)}
                          >
                            <i className="bi bi-trash" aria-hidden="true" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <Drawer open={isCreateOpen} onClose={closeCreate} title="New goal">
        <GoalForm
          accounts={accounts}
          claimedAccountIds={claimedIds(goals, null, "account_ids")}
          claimedPieIds={claimedIds(goals, null, "pie_ids")}
          onSubmit={handleCreate}
          onCancel={closeCreate}
          isSubmitting={isSaving}
          error={saveError}
        />
      </Drawer>

      <Drawer open={Boolean(editingGoal)} onClose={closeEdit} title="Edit goal">
        {editingGoal && (
          <GoalForm
            initialValues={editingGoal}
            accounts={accounts}
            claimedAccountIds={claimedIds(goals, editingGoal.id, "account_ids")}
            claimedPieIds={claimedIds(goals, editingGoal.id, "pie_ids")}
            onSubmit={handleEdit}
            onCancel={closeEdit}
            isSubmitting={isEditSaving}
            error={editSaveError}
          />
        )}
      </Drawer>

      <ConfirmDialog
        open={Boolean(deletingGoal)}
        title="Delete goal"
        message="This will permanently delete the goal. This can't be undone."
        confirmLabel="Delete goal"
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

export default GoalsListPage;
