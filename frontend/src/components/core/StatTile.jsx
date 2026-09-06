import "./StatTile.css";

/**
 * A labeled number tile for page-level summary stats (AccountDetailPage's/
 * PieDetailPage's Total Invested/Profit-Loss/Profit-Loss % row). `hint`
 * renders below the value in muted text (e.g. "Sample data" while these
 * aren't yet computed from real pricing/transaction data). `tone`
 * ("is-up"/"is-down"/"is-flat", see sampleFinancials.js's `plTone`)
 * colors the value green/red/muted for a P&L figure — omit it for a
 * plain, uncolored stat like Total Invested. `hintTone` applies that same
 * coloring to the hint instead (e.g. a Profit/loss tile's % hint following
 * the same sign as its amount value) — independent of `tone` since a hint
 * like "Invested $X" is plain even when the tile's own value is toned.
 */
function StatTile({ label, value, hint, tone, hintTone }) {
  return (
    <div className="ec-stat-tile">
      <span className="ec-stat-label">{label}</span>
      <span className={`ec-stat-value${tone ? ` ${tone}` : ""}`}>{value}</span>
      {hint && <span className={`ec-stat-hint${hintTone ? ` ${hintTone}` : ""}`}>{hint}</span>}
    </div>
  );
}

export default StatTile;
