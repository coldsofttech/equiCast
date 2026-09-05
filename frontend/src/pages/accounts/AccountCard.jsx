import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";
import {
  formatCurrency,
  buildPieSample,
  buildHoldingSample,
  aggregateSamples,
  plTone,
} from "../sampleFinancials.js";

/**
 * One account's summary card — shared by AccountsListPage's full list and
 * DashboardPage's landing overview so the two render the same markup
 * instead of two copies drifting apart. Current value/P&L are sample data
 * (see sampleFinancials.js) — equiCast doesn't compute real portfolio
 * valuation yet.
 */
function AccountCard({ account, onClick }) {
  const pies = account.pies ?? [];
  const directHoldings = account.holdings ?? [];
  const holdingsCount = directHoldings.length + pies.reduce((sum, p) => sum + (p.holdings?.length ?? 0), 0);
  const totals = aggregateSamples([
    ...pies.map((p) => buildPieSample(p.id)),
    ...directHoldings.map((h) => buildHoldingSample(h.id)),
  ]);
  const tone = plTone(totals.plPct);
  const plSign = totals.plValue >= 0 ? "+" : "-";

  return (
    <Card
      className="ec-account-card"
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onClick();
        }
      }}
    >
      <div className="ec-account-card-head">
        <h2 className="ec-account-card-name">{account.name}</h2>
        <Badge tone="accent">{account.account_type}</Badge>
      </div>
      <p className="ec-account-card-desc">{account.description}</p>
      <div className="ec-account-card-value">
        <span className="ec-account-card-current">
          {formatCurrency(totals.currentValue, account.currency)}
        </span>
        <span className={`ec-account-card-pl ${tone}`}>
          {plSign}
          {formatCurrency(Math.abs(totals.plValue), account.currency)} ({plSign}
          {Math.abs(totals.plPct).toFixed(1)}%)
        </span>
      </div>
      <div className="ec-account-card-meta">
        <Badge tone="neutral">{account.currency}</Badge>
        <Badge tone={account.transaction_type === "TRANSACTION" ? "purple" : "info"}>
          {account.transaction_type === "TRANSACTION" ? "Per-transaction" : "Average cost"}
        </Badge>
        <span className="ec-account-card-counts">
          <span className="ec-account-card-count">{pies.length} pies</span>
          <span className="ec-account-card-count">{holdingsCount} holdings</span>
        </span>
      </div>
    </Card>
  );
}

export default AccountCard;
