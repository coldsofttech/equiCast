import "./GoalProgressBar.css";

/**
 * A linear progress bar toward a goal's target — amber while short of the
 * target, green once reached (same tone-by-threshold idea as
 * AllocationEditor.jsx's `AllocationRing`, just a bar instead of a ring
 * since a goal has no "over 100% is bad" concept the way a pie's
 * allocation does — overshooting a savings goal is fine). Visually clamped
 * at a full bar past 100%; `pct` itself (unclamped) still drives the
 * `aria-valuenow`/label so an assistive reader isn't told progress capped
 * at 100 when it didn't.
 *
 * @param {{ pct: number, achieved?: boolean }} props
 */
function GoalProgressBar({ pct, achieved = false }) {
  const clamped = Math.min(Math.max(pct, 0), 100);
  const tone = achieved || pct >= 100 ? "is-achieved" : "is-active";

  return (
    <div
      className="ec-goal-progress"
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className={`ec-goal-progress-fill ${tone}`} style={{ width: `${clamped}%` }} />
    </div>
  );
}

export default GoalProgressBar;
