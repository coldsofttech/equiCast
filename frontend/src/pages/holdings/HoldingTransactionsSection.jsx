import { useState } from "react";
import Badge from "../../components/core/Badge.jsx";
import Balance from "../../components/core/Balance.jsx";
import Card from "../../components/core/Card.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import { TextField, SelectField } from "../../components/core/Field.jsx";
import {
  MAX_RECENT_TRANSACTIONS,
  formatPrice,
  selectNetShares,
  selectPositionEntry,
  selectRecentTradeTransactions,
} from "./holdingFinancials.js";

/** A plain "YYYY-MM-DD" date string as "10 Sep 2026" — same short format
 * HoldingDividendsSection's formatDividendDate uses. */
function formatTransactionDate(isoDate) {
  if (!isoDate) return "—";
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** Bootstrap icon + Badge tone per AVERAGE-mode entry type. A legacy record
 * predating the BUY/DIVIDEND shape has `type: null` — treated as "BUY"
 * everywhere, same as the backend does (see equicast_core.transactions). */
const AVERAGE_TYPE_META = {
  BUY: { icon: "bi-cart-plus", label: "Buy", tone: "success" },
  DIVIDEND: { icon: "bi-cash-coin", label: "Dividend", tone: "info" },
};

function averageTypeMeta(type) {
  return AVERAGE_TYPE_META[type] ?? AVERAGE_TYPE_META.BUY;
}

/** Date/no_of_shares/{average_price_native,price_native}/amount_native form
 * shared by "Add Buy", "Add Sell", "Add Dividend", and editing an existing
 * (mutable) entry — `type` picks which fields show, `mode` picks whether an
 * account/portfolio selector shows (only relevant when creating: editing an
 * existing entry never moves it to a different holding) and whether this
 * calls `onSubmit(holdingId, { type, ...fields })` (create) or
 * `onSubmit(holdingId, fields)` (edit, no `type` — immutable once created).
 * Only ever sends the *native*-currency value the user typed — the backend
 * resolves/stores the converted (default-currency) figure itself (see
 * equicast_core.transactions module docstring), so there's nothing for this
 * form to compute or display for that.
 *
 * `transactionType` (the user's global AVERAGE/TRANSACTION setting) only
 * matters for a BUY: an AVERAGE-mode BUY is the holding's one
 * average_price_native position entry, a TRANSACTION-mode BUY is a
 * price_native trade record. A SELL is always TRANSACTION-mode (AVERAGE
 * mode has no SELL type at all) and shares that same price_native shape. */
function TransactionForm({ type, transactionType = "AVERAGE", mode, instances, initialValues, onSubmit, onCancel }) {
  const [holdingId, setHoldingId] = useState(
    initialValues?.holdingId ?? instances[0]?.holding.id ?? ""
  );
  const [date, setDate] = useState(initialValues?.date ?? "");
  const [shares, setShares] = useState(initialValues?.no_of_shares ?? "");
  const isAverageBuy = type === "BUY" && transactionType === "AVERAGE";
  const priceFieldKey = isAverageBuy ? "average_price_native" : "price_native";
  const [price, setPrice] = useState(initialValues?.[priceFieldKey] ?? "");
  const [amount, setAmount] = useState(initialValues?.amount_native ?? "");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = (event) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    const fields =
      type === "DIVIDEND"
        ? { date, amount_native: amount }
        : { date, no_of_shares: shares, [priceFieldKey]: price };
    const payload = mode === "create" ? { type, ...fields } : fields;
    onSubmit(holdingId, payload)
      .catch((err) => setError(err.message ?? "Couldn't save this transaction."))
      .finally(() => setIsSaving(false));
  };

  return (
    <form onSubmit={handleSubmit} className="ec-form">
      {error && <Alert tone="danger">{error}</Alert>}
      {mode === "create" && (
        <SelectField
          id="transaction-holding"
          label="Account"
          required
          value={holdingId}
          onChange={(event) => setHoldingId(event.target.value)}
        >
          {instances.map((instance) => (
            <option key={instance.holding.id} value={instance.holding.id}>
              {instance.location}
            </option>
          ))}
        </SelectField>
      )}
      <TextField
        id="transaction-date"
        label="Date"
        type="date"
        required
        value={date}
        onChange={(event) => setDate(event.target.value)}
      />
      {type === "DIVIDEND" ? (
        <TextField
          id="transaction-amount"
          label="Amount received"
          type="number"
          min="0.01"
          step="0.01"
          required
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          hint="Total cash received, in this holding's native currency."
        />
      ) : (
        <>
          <TextField
            id="transaction-shares"
            label="No of shares"
            type="number"
            min="0.000001"
            step="any"
            required
            value={shares}
            onChange={(event) => setShares(event.target.value)}
          />
          <TextField
            id="transaction-price"
            label={isAverageBuy ? "Average price (native)" : "Price (native)"}
            type="number"
            min="0.01"
            step="0.01"
            required
            value={price}
            onChange={(event) => setPrice(event.target.value)}
          />
        </>
      )}
      <div className="ec-form-actions">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isSaving}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" isLoading={isSaving}>
          {mode === "create" ? "Add" : "Save"}
        </Button>
      </div>
    </form>
  );
}

/** One BUY/DIVIDEND card or table row's total value, in native currency —
 * shares * avg price for a BUY, the cash amount for a DIVIDEND. */
function averageEntryTotal(transaction) {
  const type = transaction.type ?? "BUY";
  return type === "DIVIDEND"
    ? Number(transaction.amount_native)
    : Number(transaction.no_of_shares) * Number(transaction.average_price_native);
}

/** One AVERAGE-mode entry (BUY or DIVIDEND) in the top-5 list — a single
 * row: icon-only type badge, date, total value, edit, delete. */
function AverageEntryCard({ transaction, nativeCurrency, onEdit, onDelete }) {
  const type = transaction.type ?? "BUY";
  const meta = averageTypeMeta(type);

  return (
    <div className="ec-transaction-row-card">
      <Badge tone={meta.tone} title={meta.label} aria-label={meta.label}>
        <i className={`bi ${meta.icon}`} aria-hidden="true" />
      </Badge>
      <span className="ec-transaction-row-date">{formatTransactionDate(transaction.date)}</span>
      <Balance as="span" className="ec-transaction-row-value">
        {formatPrice(averageEntryTotal(transaction), nativeCurrency)}
      </Balance>
      <div className="ec-table-actions">
        <button type="button" className="ec-icon-btn" aria-label="Edit transaction" onClick={onEdit}>
          <i className="bi bi-pencil" aria-hidden="true" />
        </button>
        <button
          type="button"
          className="ec-icon-btn ec-icon-btn--danger"
          aria-label="Delete transaction"
          onClick={onDelete}
        >
          <i className="bi bi-trash" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

/** One BUY/SELL trade card for TRANSACTION-mode holdings. Deletable (the
 * only way to correct a mistaken entry, since these records are immutable —
 * no edit) via `onDelete`. */
function TradeCard({ transaction, nativeCurrency, location, onDelete }) {
  return (
    <div className="ec-dividend-card">
      <div className="ec-transaction-card-head">
        <Badge tone={transaction.type === "SELL" ? "danger" : "success"}>{transaction.type}</Badge>
        {location && <span className="ec-transaction-card-location">{location}</span>}
        <div className="ec-table-actions">
          <button
            type="button"
            className="ec-icon-btn ec-icon-btn--danger"
            aria-label="Delete transaction"
            onClick={onDelete}
          >
            <i className="bi bi-trash" aria-hidden="true" />
          </button>
        </div>
      </div>
      <div className="ec-dividend-fields-row">
        <div className="ec-dividend-field">
          <span className="ec-dividend-field-label">Date</span>
          <span className="ec-dividend-field-value">
            {formatTransactionDate(transaction.date)}
          </span>
        </div>
        <div className="ec-dividend-field">
          <span className="ec-dividend-field-label">Shares</span>
          <span className="ec-dividend-field-value">{transaction.no_of_shares}</span>
        </div>
        <div className="ec-dividend-field">
          <span className="ec-dividend-field-label">Price (native)</span>
          <span className="ec-dividend-field-value">
            <Balance>{formatPrice(Number(transaction.price_native), nativeCurrency)}</Balance>
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Transactions panel, below Dividends on the holding detail page. Shape
 * depends on the user's single global transaction_type (see
 * api/identity.js's UserProfile — no per-instance mode anymore):
 *
 * - AVERAGE: header actions "Add Buy"/"Add Dividend"/"See all" (all open a
 *   Drawer — see `TransactionForm` and the "See all" table below), a top-5
 *   grid of the most recent BUY/DIVIDEND entries merged across every
 *   instance of this ticker (a location tag appears only when the ticker
 *   has more than one instance), each editable/deletable in place. "Add
 *   Buy" only offers instances that don't already have a BUY recorded (one
 *   per holding, see equicast_core.transactions); "Add Dividend" offers
 *   every instance, since dividends are uncapped.
 * - TRANSACTION: header actions "Add Buy"/"Add Sell"/"See all", up to
 *   MAX_RECENT_TRANSACTIONS most recent BUY/SELL cards merged across every
 *   instance of this ticker, plus a "See all" drawer with the full history
 *   table. Records are immutable once created (no edit — mirrors
 *   equicast_core.transactions), but deletable, same as an AVERAGE-mode
 *   entry — the only way to correct a mistaken one. "Add Sell" only offers
 *   instances with net shares > 0 recorded (see `selectNetShares`); "Add
 *   Buy" offers every instance, since TRANSACTION-mode BUYs are uncapped.
 *   Auto-populating a TRANSACTION-mode dividend from market data is planned
 *   as a separate scheduled job, not built here (see the parked
 *   auto-populate feature).
 *
 * `instances`/`transactionsByHolding` are already fetched at the page
 * level (see HoldingTickerPage.jsx) — this component takes them as props
 * rather than fetching itself, same convention HoldingDividendsSection
 * uses for its own `dividends` prop.
 *
 * @param {{
 *   instances: { holding: { id: string }, location: string }[],
 *   transactionsByHolding: Record<string, { transactions: import("../../api/transactions.js").Transaction[], error: boolean }>,
 *   transactionType: "AVERAGE"|"TRANSACTION",
 *   nativeCurrency: string|null,
 *   onCreateTransaction: (holdingId: string, fields: object) => Promise<unknown>,
 *   onUpdateTransaction: (holdingId: string, transactionId: string, fields: object) => Promise<unknown>,
 *   onDeleteTransaction: (holdingId: string, transactionId: string) => Promise<unknown>,
 * }} props
 */
function HoldingTransactionsSection({
  instances,
  transactionsByHolding,
  transactionType,
  nativeCurrency,
  onCreateTransaction,
  onUpdateTransaction,
  onDeleteTransaction,
  onLoadMoreTransactions,
}) {
  const [drawer, setDrawer] = useState(null); // null | "add-buy" | "add-dividend" | "see-all" | { kind: "edit", holdingId, transaction }
  const [deleting, setDeleting] = useState(null); // null | { holdingId, transactionId }
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const closeDrawer = () => setDrawer(null);

  const validInstances = instances.filter((instance) => !transactionsByHolding[instance.holding.id]?.error);
  if (validInstances.length === 0) return null;

  const showLocation = validInstances.length > 1;

  const handleDelete = () => {
    setIsDeleting(true);
    setDeleteError(null);
    onDeleteTransaction(deleting.holdingId, deleting.transactionId)
      .then(() => setDeleting(null))
      .catch((err) => setDeleteError(err.message ?? "Couldn't delete this transaction."))
      .finally(() => setIsDeleting(false));
  };

  // "See all"'s next page — one instance's own `next` (see
  // HoldingTickerPage.jsx's handleLoadMoreTransactions) tells whether *that*
  // holding has more; this section merges every instance's rows into one
  // table, so "more to load" means *any* of them still does. Loads every
  // instance with more in parallel and lets each one's own state update
  // land as it resolves, rather than paging one instance at a time.
  const instancesWithMore = validInstances.filter(
    (instance) => transactionsByHolding[instance.holding.id]?.next != null
  );
  const handleLoadMore = () => {
    setIsLoadingMore(true);
    Promise.all(instancesWithMore.map((instance) => onLoadMoreTransactions(instance.holding.id))).finally(
      () => setIsLoadingMore(false)
    );
  };
  const loadMoreControl = instancesWithMore.length > 0 && (
    <div className="ec-table-load-more">
      <Button variant="secondary" onClick={handleLoadMore} isLoading={isLoadingMore}>
        Load more
      </Button>
    </div>
  );

  if (transactionType === "AVERAGE") {
    const merged = validInstances.flatMap((instance) =>
      (transactionsByHolding[instance.holding.id]?.transactions ?? [])
        .filter((t) => t.type === "BUY" || t.type === "DIVIDEND" || t.type == null)
        .map((transaction) => ({ transaction, holdingId: instance.holding.id, location: instance.location }))
    );
    const sorted = [...merged].sort((a, b) =>
      (b.transaction.date ?? "").localeCompare(a.transaction.date ?? "")
    );
    const top5 = sorted.slice(0, MAX_RECENT_TRANSACTIONS);
    const buyEligibleInstances = validInstances.filter(
      (instance) => !selectPositionEntry(transactionsByHolding[instance.holding.id]?.transactions ?? [])
    );

    return (
      <Card className="ec-detail-section">
        <div className="ec-section-head">
          <h3 className="ec-section-title">Transactions</h3>
          <div className="ec-section-head-actions">
            <button type="button" className="ec-inline-link-btn" onClick={() => setDrawer("add-buy")}>
              Add Buy
            </button>
            <button type="button" className="ec-inline-link-btn" onClick={() => setDrawer("add-dividend")}>
              Add Dividend
            </button>
            <button type="button" className="ec-inline-link-btn" onClick={() => setDrawer("see-all")}>
              See all
            </button>
          </div>
        </div>

        {top5.length > 0 ? (
          <div className="ec-transaction-row-list">
            {top5.map(({ transaction, holdingId }) => (
              <AverageEntryCard
                key={transaction.id}
                transaction={transaction}
                nativeCurrency={nativeCurrency}
                onEdit={() => setDrawer({ kind: "edit", holdingId, transaction })}
                onDelete={() => setDeleting({ holdingId, transactionId: transaction.id })}
              />
            ))}
          </div>
        ) : (
          <p className="ec-chart-caption">No transactions recorded yet.</p>
        )}

        <Drawer open={drawer === "add-buy"} onClose={closeDrawer} title="Add Buy">
          {buyEligibleInstances.length > 0 ? (
            <TransactionForm
              type="BUY"
              mode="create"
              instances={buyEligibleInstances}
              onSubmit={(holdingId, fields) => onCreateTransaction(holdingId, fields).then(closeDrawer)}
              onCancel={closeDrawer}
            />
          ) : (
            <p className="ec-chart-caption">
              Every one of your holdings for this ticker already has a purchase recorded — edit it
              from See all instead.
            </p>
          )}
        </Drawer>

        <Drawer open={drawer === "add-dividend"} onClose={closeDrawer} title="Add Dividend">
          <TransactionForm
            type="DIVIDEND"
            mode="create"
            instances={validInstances}
            onSubmit={(holdingId, fields) => onCreateTransaction(holdingId, fields).then(closeDrawer)}
            onCancel={closeDrawer}
          />
        </Drawer>

        <Drawer
          open={Boolean(drawer && drawer.kind === "edit")}
          onClose={closeDrawer}
          title={drawer?.kind === "edit" ? `Edit ${averageTypeMeta(drawer.transaction.type ?? "BUY").label}` : ""}
        >
          {drawer?.kind === "edit" && (
            <TransactionForm
              type={drawer.transaction.type ?? "BUY"}
              mode="edit"
              instances={[]}
              initialValues={drawer.transaction}
              onSubmit={(holdingId, fields) =>
                onUpdateTransaction(drawer.holdingId, drawer.transaction.id, fields).then(closeDrawer)
              }
              onCancel={closeDrawer}
            />
          )}
        </Drawer>

        <Drawer open={drawer === "see-all"} onClose={closeDrawer} title="Transactions">
          <div className="ec-table-wrap">
            <table className="ec-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Date</th>
                  <th>Shares</th>
                  <th>Avg price (native)</th>
                  <th>Total value</th>
                  {showLocation && <th>Location</th>}
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {sorted.map(({ transaction, holdingId, location }) => {
                  const type = transaction.type ?? "BUY";
                  const meta = averageTypeMeta(type);
                  return (
                    <tr key={transaction.id}>
                      <td>
                        <Badge tone={meta.tone}>
                          <i className={`bi ${meta.icon}`} aria-hidden="true" /> {meta.label}
                        </Badge>
                      </td>
                      <td>{formatTransactionDate(transaction.date)}</td>
                      <td>{type === "BUY" ? transaction.no_of_shares : "—"}</td>
                      <td>
                        {type === "BUY" ? (
                          <Balance>
                            {formatPrice(Number(transaction.average_price_native), nativeCurrency)}
                          </Balance>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        <Balance>{formatPrice(averageEntryTotal(transaction), nativeCurrency)}</Balance>
                      </td>
                      {showLocation && <td>{location}</td>}
                      <td>
                        <div className="ec-table-actions">
                          <button
                            type="button"
                            className="ec-icon-btn"
                            aria-label="Edit transaction"
                            onClick={() => setDrawer({ kind: "edit", holdingId, transaction })}
                          >
                            <i className="bi bi-pencil" aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            className="ec-icon-btn ec-icon-btn--danger"
                            aria-label="Delete transaction"
                            onClick={() => setDeleting({ holdingId, transactionId: transaction.id })}
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
          {loadMoreControl}
        </Drawer>

        <ConfirmDialog
          open={Boolean(deleting)}
          title="Delete transaction"
          message={deleteError ?? "This can't be undone."}
          isLoading={isDeleting}
          onConfirm={handleDelete}
          onCancel={() => {
            setDeleting(null);
            setDeleteError(null);
          }}
        />
      </Card>
    );
  }

  const allTransactions = validInstances.flatMap((instance) =>
    (transactionsByHolding[instance.holding.id]?.transactions ?? []).map((transaction) => ({
      transaction,
      holdingId: instance.holding.id,
      location: instance.location,
    }))
  );
  const recent = selectRecentTradeTransactions(allTransactions.map((entry) => entry.transaction));
  const recentWithContext = recent.map((transaction) => {
    const match = allTransactions.find((entry) => entry.transaction.id === transaction.id);
    return { transaction, holdingId: match?.holdingId, location: match?.location };
  });
  const fullHistory = [...allTransactions]
    .filter((entry) => entry.transaction.type === "BUY" || entry.transaction.type === "SELL")
    .sort((a, b) => (b.transaction.date ?? "").localeCompare(a.transaction.date ?? ""));
  const sellEligibleInstances = validInstances.filter(
    (instance) =>
      selectNetShares(transactionsByHolding[instance.holding.id]?.transactions ?? []) > 0
  );

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">Transactions</h3>
        <div className="ec-section-head-actions">
          <button type="button" className="ec-inline-link-btn" onClick={() => setDrawer("add-buy")}>
            Add Buy
          </button>
          <button type="button" className="ec-inline-link-btn" onClick={() => setDrawer("add-sell")}>
            Add Sell
          </button>
          {fullHistory.length > recent.length && (
            <button type="button" className="ec-inline-link-btn" onClick={() => setDrawer("see-all")}>
              See all
            </button>
          )}
        </div>
      </div>

      {recent.length > 0 ? (
        <div className="ec-dividend-grid">
          {recentWithContext.map(({ transaction, holdingId, location }) => (
            <TradeCard
              key={transaction.id}
              transaction={transaction}
              nativeCurrency={nativeCurrency}
              location={showLocation ? location : null}
              onDelete={() => setDeleting({ holdingId, transactionId: transaction.id })}
            />
          ))}
        </div>
      ) : (
        <p className="ec-chart-caption">No transactions recorded yet.</p>
      )}

      <Drawer open={drawer === "add-buy"} onClose={closeDrawer} title="Add Buy">
        <TransactionForm
          type="BUY"
          transactionType="TRANSACTION"
          mode="create"
          instances={validInstances}
          onSubmit={(holdingId, fields) => onCreateTransaction(holdingId, fields).then(closeDrawer)}
          onCancel={closeDrawer}
        />
      </Drawer>

      <Drawer open={drawer === "add-sell"} onClose={closeDrawer} title="Add Sell">
        {sellEligibleInstances.length > 0 ? (
          <TransactionForm
            type="SELL"
            transactionType="TRANSACTION"
            mode="create"
            instances={sellEligibleInstances}
            onSubmit={(holdingId, fields) => onCreateTransaction(holdingId, fields).then(closeDrawer)}
            onCancel={closeDrawer}
          />
        ) : (
          <p className="ec-chart-caption">
            None of your holdings for this ticker have any shares recorded to sell.
          </p>
        )}
      </Drawer>

      <Drawer open={drawer === "see-all"} onClose={closeDrawer} title="Transactions">
        <div className="ec-table-wrap">
          <table className="ec-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Date</th>
                <th>Shares</th>
                <th>Price (native)</th>
                {showLocation && <th>Location</th>}
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {fullHistory.map(({ transaction, holdingId, location }) => (
                <tr key={transaction.id}>
                  <td>
                    <Badge tone={transaction.type === "SELL" ? "danger" : "success"}>
                      {transaction.type}
                    </Badge>
                  </td>
                  <td>{formatTransactionDate(transaction.date)}</td>
                  <td>{transaction.no_of_shares}</td>
                  <td>
                    <Balance>{formatPrice(Number(transaction.price_native), nativeCurrency)}</Balance>
                  </td>
                  {showLocation && <td>{location}</td>}
                  <td>
                    <div className="ec-table-actions">
                      <button
                        type="button"
                        className="ec-icon-btn ec-icon-btn--danger"
                        aria-label="Delete transaction"
                        onClick={() => setDeleting({ holdingId, transactionId: transaction.id })}
                      >
                        <i className="bi bi-trash" aria-hidden="true" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {loadMoreControl}
      </Drawer>

      <ConfirmDialog
        open={Boolean(deleting)}
        title="Delete transaction"
        message={deleteError ?? "This can't be undone."}
        isLoading={isDeleting}
        onConfirm={handleDelete}
        onCancel={() => {
          setDeleting(null);
          setDeleteError(null);
        }}
      />
    </Card>
  );
}

export default HoldingTransactionsSection;
