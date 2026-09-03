import "./StatTile.css";

/**
 * A labeled number tile for page-level summary stats (AccountDetailPage's/
 * PieDetailPage's Total Invested/Profit-Loss/Profit-Loss % row). `hint`
 * renders below the value in muted text (e.g. "Sample data" while these
 * aren't yet computed from real pricing/transaction data). `tone`
 * ("is-up"/"is-down"/"is-flat", see sampleFinancials.js's `plTone`)
 * colors the value green/red/muted for a P&L figure — omit it for a
 * plain, uncolored stat like Total Invested.
 */
function StatTile({ label, value, hint, tone }) {
  return (
    <div className="ec-stat-tile">
      <span className="ec-stat-label">{label}</span>
      <span className={`ec-stat-value${tone ? ` ${tone}` : ""}`}>{value}</span>
      {hint && <span className="ec-stat-hint">{hint}</span>}
    </div>
  );
}

export default StatTile;
