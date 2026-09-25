import AssetIcon from "../../components/core/AssetIcon.jsx";
import { formatCurrency } from "../sampleFinancials.js";
import "./WatchlistEntryCard.css";

/** Green when positive, red when negative, neutral grey when flat/unknown
 * — same "is-up"/"is-down"/"is-flat" tone convention as the P&L figures
 * elsewhere (e.g. AccountCard's ec-account-card-pl). */
function changeTone(pct) {
  if (pct == null) return "is-flat";
  if (pct > 0) return "is-up";
  if (pct < 0) return "is-down";
  return "is-flat";
}

function ChangeStat({ label, pct }) {
  return (
    <span className={`ec-watchlist-card-change ${changeTone(pct)}`}>
      <span className="ec-watchlist-card-change-label">{label}</span>
      {pct != null ? `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%` : "—"}
    </span>
  );
}

/**
 * One watchlist entry as a card — a real holding (custom watchlist) or a
 * system watchlist's reference row (e.g. Global Markets — see
 * backend/watchlists/views.py's SYSTEM_WATCHLISTS/`_SYSTEM_WATCHLIST_
 * STORAGE_KEYS`), rendered identically either way: logo, name, ticker,
 * current price in the entry's own **native** currency (never the
 * caller's own default_currency — a system watchlist has no single owner
 * to convert it for, and a real holding's card here deliberately matches
 * that for visual consistency across tabs), and 1-week/1-month % change,
 * colored green/red. `current_price_native` (a real holding) takes
 * precedence over `current_price` (a system entry's own field is already
 * native — see equicast_watchlist.builder) so this works for both shapes
 * without the caller needing to know which one it has.
 *
 * A system entry has no `website` (fx/future/benchmark profiles never
 * carry one — see equicast_core.catalog.build_catalog_rows), so its logo
 * slot renders nothing; that's expected, not a bug. A system entry also
 * has no `id` (it isn't a stored Holding), so a caller keys its list off
 * `ticker` instead — only a real holding is removable, since a system
 * entry isn't something the caller added.
 *
 * @param {{
 *   holding: {
 *     id?: string, ticker: string, name?: string|null, website?: string|null,
 *     currency?: string|null, current_price?: number|null,
 *     current_price_native?: number|null, change_1w_pct?: number|null,
 *     change_1m_pct?: number|null,
 *   },
 *   isRemovable?: boolean,
 *   onRemove?: () => void,
 * }} props
 */
function WatchlistEntryCard({ holding, isRemovable, onRemove }) {
  const nativePrice = holding.current_price_native ?? holding.current_price;
  const priceLabel =
    nativePrice == null
      ? "—"
      : holding.currency
        ? formatCurrency(nativePrice, holding.currency)
        : nativePrice.toLocaleString();

  return (
    <div className="ec-watchlist-card">
      {isRemovable && (
        <button
          type="button"
          className="ec-watchlist-card-remove ec-icon-btn ec-icon-btn--danger"
          aria-label={`Remove ${holding.ticker}`}
          onClick={onRemove}
        >
          <i className="bi bi-x-lg" aria-hidden="true" />
        </button>
      )}
      <div className="ec-watchlist-card-heading">
        <AssetIcon website={holding.website} size={32} />
        <div className="ec-watchlist-card-titles">
          <span className="ec-watchlist-card-name">{holding.name || holding.ticker}</span>
          <span className="ec-watchlist-card-ticker">{holding.ticker}</span>
        </div>
      </div>
      <div className="ec-watchlist-card-price">{priceLabel}</div>
      <div className="ec-watchlist-card-changes">
        <ChangeStat label="1W" pct={holding.change_1w_pct} />
        <ChangeStat label="1M" pct={holding.change_1m_pct} />
      </div>
    </div>
  );
}

export default WatchlistEntryCard;
