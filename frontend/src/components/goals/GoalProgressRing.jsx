import "./GoalProgressRing.css";

/**
 * A small donut ring showing progress toward a goal's target — same
 * amber/green tone-by-achievement as GoalProgressBar, just a ring instead
 * of a bar so it fits a narrow table column (see AllocationEditor.jsx's
 * AllocationRing for the same stroke-dasharray technique, applied there to
 * pie allocation instead of goal progress). Visually clamped at a full
 * ring past 100%; `pct` itself (unclamped) still drives `aria-valuenow` so
 * an assistive reader isn't told progress capped at 100 when it didn't.
 *
 * @param {{ pct: number, achieved?: boolean }} props
 */
function GoalProgressRing({ pct, achieved = false }) {
  const clamped = Math.min(Math.max(pct, 0), 100);
  const radius = 14;
  const circumference = 2 * Math.PI * radius;
  const dash = (clamped / 100) * circumference;
  const tone = achieved || pct >= 100 ? "var(--ec-success)" : "var(--ec-warning)";

  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 32 32"
      className="ec-goal-progress-ring"
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <circle cx="16" cy="16" r={radius} fill="none" stroke="var(--ec-surface-2)" strokeWidth="4" />
      <circle
        cx="16"
        cy="16"
        r={radius}
        fill="none"
        stroke={tone}
        strokeWidth="4"
        strokeDasharray={`${dash} ${circumference}`}
        strokeLinecap="round"
        transform="rotate(-90 16 16)"
      />
    </svg>
  );
}

export default GoalProgressRing;
