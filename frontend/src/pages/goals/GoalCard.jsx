import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";
import Balance from "../../components/core/Balance.jsx";
import IconBadge from "../../components/core/IconBadge.jsx";
import GoalProgressBar from "../../components/goals/GoalProgressBar.jsx";
import { formatCurrency } from "../sampleFinancials.js";
import { computeGoalProgress } from "./goalFinancials.js";
import { GOAL_PURPOSE_BADGE_TONES, GOAL_PURPOSE_ICONS, GOAL_PURPOSE_LABELS } from "../../config/goalPurposes.js";
import "./Goals.css";

function formatTargetDate(isoDate) {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/**
 * One goal's summary card — used by DashboardPage's goals widget, same
 * "clickable Card, real current value" shape as AccountCard.jsx. Progress
 * is `computeGoalProgress` (client-side, off the already-cached `accounts`
 * tree — see goalFinancials.js), never a value from the API itself.
 *
 * @param {{ goal: import("../../api/goals.js").Goal, accounts: import("../../api/accounts.js").Account[], defaultCurrency: string, onClick?: () => void }} props
 */
function GoalCard({ goal, accounts, defaultCurrency, onClick }) {
  const { currentValue, progressPct, isAchieved } = computeGoalProgress(goal, accounts);
  const purposeLabel =
    goal.purpose === "other" ? goal.custom_purpose || "Other" : GOAL_PURPOSE_LABELS[goal.purpose];
  const targetDate = goal.target_date && formatTargetDate(goal.target_date);

  return (
    <Card
      className="ec-account-card"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick?.();
        }
      }}
    >
      <div className="ec-goal-card-head">
        <div className="ec-goal-card-title">
          <IconBadge icon={GOAL_PURPOSE_ICONS[goal.purpose]} defaultIcon="flag-fill" size={28} />
          <h2 className="ec-account-card-name">{goal.name}</h2>
        </div>
        <Badge tone={goal.status === "achieved" ? "success" : GOAL_PURPOSE_BADGE_TONES[goal.purpose]}>
          {goal.status === "achieved" ? "Achieved" : purposeLabel}
        </Badge>
      </div>

      <div className="ec-account-card-value">
        <Balance className="ec-account-card-current">{formatCurrency(currentValue, defaultCurrency)}</Balance>
        <span className="ec-goal-card-progress-row">
          <span>{Math.round(progressPct)}% of {formatCurrency(goal.target_amount, defaultCurrency)}</span>
        </span>
      </div>

      <GoalProgressBar pct={progressPct} achieved={isAchieved} />

      {targetDate && <span className="ec-goal-card-target-date">Target: {targetDate}</span>}
    </Card>
  );
}

export default GoalCard;
