import Card from "../../components/core/Card.jsx";
import Badge from "../../components/core/Badge.jsx";

/**
 * One account's summary card — shared by AccountsListPage's full list and
 * DashboardPage's landing overview so the two render the same markup
 * instead of two copies drifting apart.
 */
function AccountCard({ account, onClick }) {
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
      <div className="ec-account-card-meta">
        <Badge tone="neutral">{account.currency}</Badge>
        <Badge tone={account.transaction_type === "TRANSACTION" ? "purple" : "info"}>
          {account.transaction_type === "TRANSACTION" ? "Per-transaction" : "Average cost"}
        </Badge>
        <span className="ec-account-card-count">{(account.pies ?? []).length} pies</span>
      </div>
    </Card>
  );
}

export default AccountCard;
