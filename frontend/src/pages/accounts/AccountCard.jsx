import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";
import Balance from "../../components/core/Balance.jsx";
import IconBadge from "../../components/core/IconBadge.jsx";
import { formatCurrency, plTone } from "../sampleFinancials.js";
import { computeHoldingValuation, summarizeHoldingValuations } from "../holdingValuation.js";
import { DEFAULT_ACCOUNT_ICON } from "../../config/accountIcons.js";

/** Same fallback `AccountDetailPage.jsx` uses before `useCurrentUser()`
 * resolves — an account has no `currency` of its own (removed — GitHub
 * issues #98/#115), so there's no per-account value to fall back to
 * instead. */
const FALLBACK_CURRENCY = "USD";

/**
 * One account's summary card — used by DashboardPage's landing overview
 * (AccountsListPage renders its own table rows, not this card). Current
 * value/P&L are real, from each holding's enriched `current_price` (see
 * holdingValuation.js's `computeHoldingValuation`, same one AccountDetailPage
 * uses) rather than sample data, summed across direct and pie-nested
 * holdings alike — same "invested" fallback when a ticker has no live
 * price. `defaultCurrency` is the user's own profile currency, since
 * that's what `current_price` is already converted to server-side.
 */
function AccountCard({ account, onClick, defaultCurrency }) {
  const pies = account.pies ?? [];
  const directHoldings = account.holdings ?? [];
  const allHoldings = [...directHoldings, ...pies.flatMap((p) => p.holdings ?? [])];
  const holdingsCount = allHoldings.length;
  const valuations = allHoldings.map(computeHoldingValuation);
  const totals = summarizeHoldingValuations(allHoldings, valuations);
  const currency = defaultCurrency ?? FALLBACK_CURRENCY;
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
        <div className="ec-account-card-title">
          <IconBadge icon={account.icon} defaultIcon={DEFAULT_ACCOUNT_ICON} size={28} />
          <h2 className="ec-account-card-name">{account.name}</h2>
        </div>
        <Badge tone="accent">{account.account_type}</Badge>
      </div>
      <p className="ec-account-card-desc">{account.description}</p>
      <div className="ec-account-card-value">
        <Balance className="ec-account-card-current">
          {formatCurrency(totals.currentValue, currency)}
        </Balance>
        <span className={`ec-account-card-pl ${tone}`}>
          <Balance>
            {plSign}
            {formatCurrency(Math.abs(totals.plValue), currency)}
          </Balance>{" "}
          ({plSign}
          {Math.abs(totals.plPct).toFixed(1)}%)
        </span>
      </div>
      <div className="ec-account-card-meta">
        <span className="ec-account-card-counts">
          <span className="ec-account-card-count">{pies.length} pies</span>
          <span className="ec-account-card-count">{holdingsCount} holdings</span>
        </span>
      </div>
    </Card>
  );
}

export default AccountCard;
