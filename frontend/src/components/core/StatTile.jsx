import "./StatTile.css";

/**
 * A labeled number tile for page-level summary stats (AccountDetailPage's
 * Total Invested/Profit-Loss/Profit-Loss % row). `hint` renders below the
 * value in muted text — used for "Coming soon" while these stay
 * placeholders, not yet computed from real pricing/transaction data.
 */
function StatTile({ label, value, hint }) {
  return (
    <div className="ec-stat-tile">
      <span className="ec-stat-label">{label}</span>
      <span className="ec-stat-value">{value}</span>
      {hint && <span className="ec-stat-hint">{hint}</span>}
    </div>
  );
}

export default StatTile;
