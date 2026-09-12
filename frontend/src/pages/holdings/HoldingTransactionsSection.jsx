import { useEffect, useState } from "react";
import Badge from "../../components/core/Badge.jsx";
import Balance from "../../components/core/Balance.jsx";
import Card from "../../components/core/Card.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import ConfirmDialog from "../../components/core/ConfirmDialog.jsx";
import { TextField, SelectField } from "../../components/core/Field.jsx";
import { useApi } from "../../api/useApi.js";
import {
  MAX_RECENT_TRANSACTIONS,
  formatFxRatio,
  formatPrice,
  resolveFxRateOnDate,
  selectNetShares,
  selectPositionEntry,
  selectRecentTransactions,
} from "./holdingFinancials.js";

/** A complete "YYYY-MM-DD" with a plausible year — guards the FX
 * auto-fill effect below against firing (even just a local lookup, no
 * longer a network call) for every partial value a native
 * `<input type="date">` reports while its year segment is still being
 * typed digit by digit (e.g. "0002" → "0020" → "0202" → "2026"). */
function isCompleteDate(date) {
  return /^\d{4}-\d{2}-\d{2}$/.test(date) && Number(date.slice(0, 4)) >= 1990;
}

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

/** Bootstrap icon + Badge tone per TRANSACTION-mode entry type — mirrors
 * AVERAGE_TYPE_META so BUY/SELL rows read the same way AVERAGE-mode's
 * BUY/DIVIDEND rows do. */
const TRADE_TYPE_META = {
  BUY: { icon: "bi-cart-plus", label: "Buy", tone: "success" },
  SELL: { icon: "bi-cart-dash", label: "Sell", tone: "danger" },
  DIVIDEND: { icon: "bi-cash-coin", label: "Dividend", tone: "info" },
};

function tradeTypeMeta(type) {
  return TRADE_TYPE_META[type] ?? TRADE_TYPE_META.BUY;
}

/** Date/no_of_shares/{average_price_native,price_native}/amount_native/
 * fx_rate form shared by "Add Buy", "Add Sell", "Add Dividend", and
 * editing an existing (mutable) entry — `type` picks which fields show,
 * `mode` picks whether an account/portfolio selector shows (only relevant
 * when creating: editing an existing entry never moves it to a different
 * holding) and whether this calls `onSubmit(holdingId, { type, ...fields })`
 * (create) or `onSubmit(holdingId, fields)` (edit, no `type` — immutable
 * once created). Sends the *native*-currency value the user typed, plus an
 * optional `fx_rate` (GitHub issue #149) — the backend resolves/stores the
 * converted (default-currency) figure itself either way (see
 * equicast_core.transactions module docstring), so this form never
 * computes or displays a converted value, only the rate used to get there.
 *
 * `transactionType` (the user's global AVERAGE/TRANSACTION setting) only
 * matters for a BUY: an AVERAGE-mode BUY is the holding's one
 * average_price_native position entry, a TRANSACTION-mode BUY is a
 * price_native trade record. A SELL is always TRANSACTION-mode (AVERAGE
 * mode has no SELL type at all) and shares that same price_native shape.
 *
 * `nativeCurrency`/`defaultCurrency` gate the FX rate field: shown only
 * when both are known and differ (a same-currency holding has nothing to
 * convert). Once shown, it auto-fills from `resolveFxRateOnDate` for
 * whichever complete `date` is entered (see `isCompleteDate` — a native
 * `<input type="date">` reports a string of partial-year values while
 * that segment is still being typed, which this ignores) — the same
 * historical rate the backend would otherwise auto-resolve, computed
 * client-side from the pair's own already-fetched price history rather
 * than a network call per date, letting the user preview and override it
 * before saving; `fxRateTouched` stops that auto-fill from clobbering a
 * manual edit once the user has actually typed into the field themselves.
 *
 * The field itself shows/accepts the rate default→native (e.g. "£1 =
 * $1.27"), matching how brokerage apps like Trading 212/Chip quote it —
 * `fx_rate` is fetched/edited in that direction, then inverted (1/rate)
 * right before it's sent as the `fx_rate` override, since that field is
 * stored/used server-side native→default (`converted_value = native_value
 * * fx_rate` — see equicast_core.transactions/resolve_converted_amounts).
 * Editing an existing entry inverts the other way on load, so its already-
 * stored native→default `fx_rate` still shows correctly in this form's
 * default→native direction. */
function TransactionForm({
  type,
  transactionType = "AVERAGE",
  mode,
  instances,
  transactionsByHolding = {},
  initialValues,
  nativeCurrency,
  defaultCurrency,
  onSubmit,
  onCancel,
}) {
  const api = useApi();
  const [holdingId, setHoldingId] = useState(
    initialValues?.holdingId ?? instances[0]?.holding.id ?? ""
  );
  const [date, setDate] = useState(initialValues?.date ?? "");
  const [shares, setShares] = useState(initialValues?.no_of_shares ?? "");
  const isAverageBuy = type === "BUY" && transactionType === "AVERAGE";
  const priceFieldKey = isAverageBuy ? "average_price_native" : "price_native";
  // TRANSACTION mode: a new BUY/SELL dated on or before this holding's
  // latest recorded trade reopens the auto-dividend watermark (see
  // TransactionsClient.rewind_dividends_synced_through) the same way
  // backdating an AVERAGE-mode BUY does — warn the same way here too.
  const isTransactionTrade =
    mode === "create" && transactionType === "TRANSACTION" && (type === "BUY" || type === "SELL");
  const latestTradeDate = isTransactionTrade
    ? (transactionsByHolding[holdingId]?.transactions ?? [])
        .filter((t) => t.type === "BUY" || t.type === "SELL")
        .reduce((latest, t) => (t.date && (!latest || t.date > latest) ? t.date : latest), null)
    : null;
  const isBackdatedTrade =
    isTransactionTrade && latestTradeDate != null && isCompleteDate(date) && date <= latestTradeDate;
  const [price, setPrice] = useState(initialValues?.[priceFieldKey] ?? "");
  const [amount, setAmount] = useState(initialValues?.amount_native ?? "");
  // `initialValues.fx_rate` (when editing) is always stored native→default
  // (see equicast_core.transactions/resolve_converted_amounts — that
  // direction is what `converted_value = native_value * fx_rate` actually
  // uses), so it's inverted here to seed the field in the default→native
  // direction this form shows/accepts (GitHub issue #149's follow-up: a
  // rate like "£1 = $1.27" reads the way brokerage apps quote it, rather
  // than "$1 = £0.79").
  const [fxRate, setFxRate] = useState(
    initialValues?.fx_rate ? String(1 / Number(initialValues.fx_rate)) : ""
  );
  const [fxRateTouched, setFxRateTouched] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const showFxField = Boolean(nativeCurrency && defaultCurrency && nativeCurrency !== defaultCurrency);

  useEffect(() => {
    if (!showFxField || !isCompleteDate(date) || fxRateTouched) return undefined;
    let cancelled = false;
    // default→native (e.g. GBP→USD), not native→default — the direction
    // this field displays/accepts, matching how brokerage apps like
    // Trading 212/Chip quote a rate (£1 = $xxx) rather than $1 = £xxx.
    // Resolved from each pair's own already-fetched/cached price history
    // (see resolveFxRateOnDate) — no network call per date typed.
    resolveFxRateOnDate(api, defaultCurrency, nativeCurrency, date).then((rate) => {
      if (cancelled) return;
      // `null` (no rate published for this pair/date) leaves the field
      // blank; the backend still auto-resolves its own attempt on submit
      // if the user doesn't type one in themselves.
      if (rate != null) setFxRate(String(rate));
    });
    return () => {
      cancelled = true;
    };
  }, [api, showFxField, date, nativeCurrency, defaultCurrency, fxRateTouched]);

  const handleSubmit = (event) => {
    event.preventDefault();
    setIsSaving(true);
    setError(null);
    // Sent to the backend inverted, back to the native→default direction
    // `fx_rate` is actually stored/used in (see the `fxRate` state comment
    // above) — this field shows/accepts the reciprocal for display only.
    const fxFields = fxRate !== "" ? { fx_rate: String(1 / Number(fxRate)) } : {};
    const fields =
      type === "DIVIDEND"
        ? { date, amount_native: amount, ...fxFields }
        : { date, no_of_shares: shares, [priceFieldKey]: price, ...fxFields };
    const payload = mode === "create" ? { type, ...fields } : fields;
    onSubmit(holdingId, payload)
      .catch((err) => setError(err.message ?? "Couldn't save this transaction."))
      .finally(() => setIsSaving(false));
  };

  return (
    <form onSubmit={handleSubmit} className="ec-form">
      {error && <Alert tone="danger">{error}</Alert>}
      {mode === "edit" && isAverageBuy && (
        <Alert tone="info">
          Changing the date or no of shares here rebuilds this holding&rsquo;s dividend history from
          scratch — any dividend you edited or deleted by hand will be regenerated. Review it
          afterward if that&rsquo;s not what you want.
        </Alert>
      )}
      {isBackdatedTrade && (
        <Alert tone="info">
          This is dated on or before your latest recorded trade for this holding, so it rebuilds
          this holding&rsquo;s whole dividend history from scratch against the corrected share
          count — any dividend you edited or deleted by hand will be regenerated. Review it
          afterward if that&rsquo;s not what you want.
        </Alert>
      )}
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
      {showFxField && (
        <TextField
          id="transaction-fx-rate"
          label={`FX rate (${defaultCurrency} → ${nativeCurrency})`}
          type="number"
          min="0.000001"
          step="any"
          value={fxRate}
          onChange={(event) => {
            setFxRate(event.target.value);
            setFxRateTouched(true);
          }}
          hint="Defaults to the historical rate for this date — override if needed."
        />
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

/** Same total as `averageEntryTotal`, but in the user's default currency —
 * `average_price`/`amount` are `average_price_native`/`amount_native`'s
 * already-converted counterparts (see api/transactions.js's Transaction
 * typedef), so no client-side conversion is needed here. `null` when
 * `fx_rate` couldn't be resolved for this entry (see equicast_core.
 * transactions/resolve_converted_amounts) and so neither was this. */
function averageEntryTotalConverted(transaction) {
  const type = transaction.type ?? "BUY";
  const converted = type === "DIVIDEND" ? transaction.amount : transaction.average_price;
  if (converted == null) return null;
  return type === "DIVIDEND" ? Number(converted) : Number(transaction.no_of_shares) * Number(converted);
}

/** `transaction.fx_rate` is stored/used server-side native→default (see
 * TransactionForm's own comment on why) — inverted here for display, same
 * default→native direction ("£1 = $xxx") the form itself now shows/accepts.
 * `null` when unresolved. */
function displayFxRate(transaction) {
  return transaction.fx_rate ? 1 / Number(transaction.fx_rate) : null;
}

/** One AVERAGE-mode entry (BUY or DIVIDEND) in the top-5 list — a single
 * row: icon-only type badge, date, no of shares, FX rate, native value,
 * converted value, edit, delete. A DIVIDEND has no `no_of_shares` (only a
 * cash amount), same as the "See all" table's own "—" fallback for that
 * column. FX rate/native value only show when this holding's native
 * currency actually differs from the user's default — nothing to convert
 * otherwise, same gate `TransactionForm`'s own FX field uses. */
function AverageEntryCard({ transaction, nativeCurrency, defaultCurrency, onEdit, onDelete }) {
  const type = transaction.type ?? "BUY";
  const meta = averageTypeMeta(type);
  const showFx = Boolean(nativeCurrency && defaultCurrency && nativeCurrency !== defaultCurrency);
  const fxRate = showFx ? displayFxRate(transaction) : null;
  const convertedTotal = showFx ? averageEntryTotalConverted(transaction) : null;

  return (
    <div className="ec-transaction-row-card">
      <Badge tone={meta.tone} title={meta.label} aria-label={meta.label}>
        <i className={`bi ${meta.icon}`} aria-hidden="true" />
      </Badge>
      <span className="ec-transaction-row-date">{formatTransactionDate(transaction.date)}</span>
      <span className="ec-transaction-row-shares">
        {type === "BUY" ? transaction.no_of_shares : "—"}
      </span>
      {showFx && (
        <span className="ec-transaction-row-fx">
          {fxRate != null ? formatFxRatio(fxRate, defaultCurrency, nativeCurrency) : "—"}
        </span>
      )}
      <Balance as="span" className="ec-transaction-row-native-value">
        {formatPrice(averageEntryTotal(transaction), nativeCurrency)}
      </Balance>
      {showFx && (
        <Balance as="span" className="ec-transaction-row-value">
          {convertedTotal != null ? formatPrice(convertedTotal, defaultCurrency) : "—"}
        </Balance>
      )}
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

/** One BUY/SELL/DIVIDEND record's total value, in native currency — shares
 * * price for a trade, mirroring averageEntryTotal's BUY case, or the cash
 * amount for a DIVIDEND, mirroring its DIVIDEND case. */
function tradeEntryTotal(transaction) {
  return transaction.type === "DIVIDEND"
    ? Number(transaction.amount_native)
    : Number(transaction.no_of_shares) * Number(transaction.price_native);
}

/** Same total as `tradeEntryTotal`, but in the user's default currency —
 * mirrors `averageEntryTotalConverted`'s reasoning, just off `price`/`amount`
 * instead of `average_price`/`amount`. `null` when `fx_rate` couldn't be
 * resolved for this entry. */
function tradeEntryTotalConverted(transaction) {
  if (transaction.type === "DIVIDEND") {
    return transaction.amount != null ? Number(transaction.amount) : null;
  }
  if (transaction.price == null) return null;
  return Number(transaction.no_of_shares) * Number(transaction.price);
}

/** One BUY/SELL/DIVIDEND entry in the top-N list for TRANSACTION-mode
 * holdings — same single-row layout AverageEntryCard uses (icon-only type
 * badge, date, no of shares, FX rate, native value, converted value,
 * actions), so both modes' transactions panels read the same way. FX
 * rate/native value only show when this holding's native currency differs
 * from the user's default, same gate AverageEntryCard uses. A BUY/SELL is
 * immutable — delete-only, via `onDelete` — same as AVERAGE mode's own
 * DIVIDEND is a user-correctable fact regardless of mode, so it's editable
 * too (`onEdit`), same as AVERAGE mode's own DIVIDEND rows. */
function TradeRowCard({ transaction, nativeCurrency, defaultCurrency, location, onEdit, onDelete }) {
  const type = transaction.type;
  const meta = tradeTypeMeta(type);
  const showFx = Boolean(nativeCurrency && defaultCurrency && nativeCurrency !== defaultCurrency);
  const fxRate = showFx ? displayFxRate(transaction) : null;
  const convertedTotal = showFx ? tradeEntryTotalConverted(transaction) : null;

  return (
    <div className="ec-transaction-row-card">
      <Badge tone={meta.tone} title={meta.label} aria-label={meta.label}>
        <i className={`bi ${meta.icon}`} aria-hidden="true" />
      </Badge>
      <span className="ec-transaction-row-date">
        {formatTransactionDate(transaction.date)}
        {location && <span className="ec-transaction-card-location"> · {location}</span>}
      </span>
      <span className="ec-transaction-row-shares">{type === "DIVIDEND" ? "—" : transaction.no_of_shares}</span>
      {showFx && (
        <span className="ec-transaction-row-fx">
          {fxRate != null ? formatFxRatio(fxRate, defaultCurrency, nativeCurrency) : "—"}
        </span>
      )}
      <Balance as="span" className="ec-transaction-row-native-value">
        {formatPrice(tradeEntryTotal(transaction), nativeCurrency)}
      </Balance>
      {showFx && (
        <Balance as="span" className="ec-transaction-row-value">
          {convertedTotal != null ? formatPrice(convertedTotal, defaultCurrency) : "—"}
        </Balance>
      )}
      <div className="ec-table-actions">
        {type === "DIVIDEND" && (
          <button type="button" className="ec-icon-btn" aria-label="Edit transaction" onClick={onEdit}>
            <i className="bi bi-pencil" aria-hidden="true" />
          </button>
        )}
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
 * - TRANSACTION: header actions "Add Buy"/"Add Sell"/"Add Dividend"/"See
 *   all", up to MAX_RECENT_TRANSACTIONS most recent BUY/SELL/DIVIDEND rows
 *   (same `ec-transaction-row-list`/`ec-transaction-row-card` layout
 *   AVERAGE-mode's top-5 list uses — see `TradeRowCard`) merged across
 *   every instance of this ticker, plus a "See all" drawer with the full
 *   history table. BUY/SELL are immutable once created (no edit — mirrors
 *   equicast_core.transactions) but deletable; DIVIDEND is editable and
 *   deletable in both modes alike, same as an AVERAGE-mode entry — a
 *   dividend is a user-correctable fact regardless of mode, including the
 *   ones GitHub issue #124's auto-dividend sync creates on the user's
 *   behalf. "Add Sell" only offers instances with net shares > 0 recorded
 *   (see `selectNetShares`); "Add Buy"/"Add Dividend" offer every instance,
 *   since TRANSACTION-mode BUYs and dividends are both uncapped.
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
 *   defaultCurrency: string|null,
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
  defaultCurrency,
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
  // Gates every FX rate/native value/converted value column and field
  // (row cards, both "See all" tables, the TransactionForm's own FX
  // field) — nothing to convert when the holding's native currency
  // already matches the user's default.
  const showFx = Boolean(nativeCurrency && defaultCurrency && nativeCurrency !== defaultCurrency);

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
                defaultCurrency={defaultCurrency}
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
              nativeCurrency={nativeCurrency}
              defaultCurrency={defaultCurrency}
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
            nativeCurrency={nativeCurrency}
            defaultCurrency={defaultCurrency}
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
              nativeCurrency={nativeCurrency}
              defaultCurrency={defaultCurrency}
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
                  {showFx && <th>FX rate</th>}
                  <th>Native value</th>
                  {showFx && <th>Value</th>}
                  {showLocation && <th>Location</th>}
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {sorted.map(({ transaction, holdingId, location }) => {
                  const type = transaction.type ?? "BUY";
                  const meta = averageTypeMeta(type);
                  const fxRate = showFx ? displayFxRate(transaction) : null;
                  const convertedTotal = showFx ? averageEntryTotalConverted(transaction) : null;
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
                      {showFx && (
                        <td>{fxRate != null ? formatFxRatio(fxRate, defaultCurrency, nativeCurrency) : "—"}</td>
                      )}
                      <td>
                        <Balance>{formatPrice(averageEntryTotal(transaction), nativeCurrency)}</Balance>
                      </td>
                      {showFx && (
                        <td>
                          {convertedTotal != null ? (
                            <Balance>{formatPrice(convertedTotal, defaultCurrency)}</Balance>
                          ) : (
                            "—"
                          )}
                        </td>
                      )}
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
  const recent = selectRecentTransactions(allTransactions.map((entry) => entry.transaction));
  const recentWithContext = recent.map((transaction) => {
    const match = allTransactions.find((entry) => entry.transaction.id === transaction.id);
    return { transaction, holdingId: match?.holdingId, location: match?.location };
  });
  const fullHistory = [...allTransactions]
    .filter(
      (entry) =>
        entry.transaction.type === "BUY" ||
        entry.transaction.type === "SELL" ||
        entry.transaction.type === "DIVIDEND"
    )
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
          <button type="button" className="ec-inline-link-btn" onClick={() => setDrawer("add-dividend")}>
            Add Dividend
          </button>
          <button type="button" className="ec-inline-link-btn" onClick={() => setDrawer("see-all")}>
            See all
          </button>
        </div>
      </div>

      {recent.length > 0 ? (
        <div className="ec-transaction-row-list">
          {recentWithContext.map(({ transaction, holdingId, location }) => (
            <TradeRowCard
              key={transaction.id}
              transaction={transaction}
              nativeCurrency={nativeCurrency}
              defaultCurrency={defaultCurrency}
              location={showLocation ? location : null}
              onEdit={() => setDrawer({ kind: "edit", holdingId, transaction })}
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
          transactionsByHolding={transactionsByHolding}
          nativeCurrency={nativeCurrency}
          defaultCurrency={defaultCurrency}
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
            transactionsByHolding={transactionsByHolding}
            nativeCurrency={nativeCurrency}
            defaultCurrency={defaultCurrency}
            onSubmit={(holdingId, fields) => onCreateTransaction(holdingId, fields).then(closeDrawer)}
            onCancel={closeDrawer}
          />
        ) : (
          <p className="ec-chart-caption">
            None of your holdings for this ticker have any shares recorded to sell.
          </p>
        )}
      </Drawer>

      <Drawer open={drawer === "add-dividend"} onClose={closeDrawer} title="Add Dividend">
        <TransactionForm
          type="DIVIDEND"
          transactionType="TRANSACTION"
          mode="create"
          instances={validInstances}
          transactionsByHolding={transactionsByHolding}
          nativeCurrency={nativeCurrency}
          defaultCurrency={defaultCurrency}
          onSubmit={(holdingId, fields) => onCreateTransaction(holdingId, fields).then(closeDrawer)}
          onCancel={closeDrawer}
        />
      </Drawer>

      <Drawer
        open={Boolean(drawer && drawer.kind === "edit")}
        onClose={closeDrawer}
        title="Edit Dividend"
      >
        {drawer?.kind === "edit" && (
          <TransactionForm
            type="DIVIDEND"
            transactionType="TRANSACTION"
            mode="edit"
            instances={[]}
            initialValues={drawer.transaction}
            nativeCurrency={nativeCurrency}
            defaultCurrency={defaultCurrency}
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
                <th>Price (native)</th>
                {showFx && <th>FX rate</th>}
                <th>Native value</th>
                {showFx && <th>Value</th>}
                {showLocation && <th>Location</th>}
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {fullHistory.map(({ transaction, holdingId, location }) => {
                const meta = tradeTypeMeta(transaction.type);
                const fxRate = showFx ? displayFxRate(transaction) : null;
                const convertedTotal = showFx ? tradeEntryTotalConverted(transaction) : null;
                return (
                <tr key={transaction.id}>
                  <td>
                    <Badge tone={meta.tone}>
                      <i className={`bi ${meta.icon}`} aria-hidden="true" /> {meta.label}
                    </Badge>
                  </td>
                  <td>{formatTransactionDate(transaction.date)}</td>
                  <td>{transaction.type === "DIVIDEND" ? "—" : transaction.no_of_shares}</td>
                  <td>
                    {transaction.type === "DIVIDEND" ? (
                      "—"
                    ) : (
                      <Balance>{formatPrice(Number(transaction.price_native), nativeCurrency)}</Balance>
                    )}
                  </td>
                  {showFx && (
                    <td>{fxRate != null ? formatFxRatio(fxRate, defaultCurrency, nativeCurrency) : "—"}</td>
                  )}
                  <td>
                    <Balance>{formatPrice(tradeEntryTotal(transaction), nativeCurrency)}</Balance>
                  </td>
                  {showFx && (
                    <td>
                      {convertedTotal != null ? (
                        <Balance>{formatPrice(convertedTotal, defaultCurrency)}</Balance>
                      ) : (
                        "—"
                      )}
                    </td>
                  )}
                  {showLocation && <td>{location}</td>}
                  <td>
                    <div className="ec-table-actions">
                      {transaction.type === "DIVIDEND" && (
                        <button
                          type="button"
                          className="ec-icon-btn"
                          aria-label="Edit transaction"
                          onClick={() => setDrawer({ kind: "edit", holdingId, transaction })}
                        >
                          <i className="bi bi-pencil" aria-hidden="true" />
                        </button>
                      )}
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

export default HoldingTransactionsSection;
