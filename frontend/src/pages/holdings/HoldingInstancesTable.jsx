import { formatPrice } from "./holdingFinancials.js";

/**
 * One row per holding *instance* — the same ticker held directly in an
 * account, and/or again inside one or more pies, is a separate holding
 * record each (own id, own transactions — see HoldingTickerPage.jsx's
 * instance-enumeration memo), so each gets its own row here rather than
 * being merged into one. No per-row ConfirmDialog: clicking delete just
 * reports `instance` up to the parent page, which owns one shared dialog
 * (same "one dialog, a `deletingX` state naming its target" convention as
 * AccountsListPage.jsx).
 *
 * @param {{
 *   instances: { holding: object, location: string, destination: string, shares: number, avgPriceNative: number|null, transactionsError: boolean }[],
 *   nativeCurrency: string|null,
 *   defaultCurrency: string|null,
 *   fxRate: number|null,
 *   fxState: "loading"|"ok"|"unavailable",
 *   onDelete: (instance: object) => void,
 *   onRowClick: (instance: object) => void,
 * }} props
 */
function HoldingInstancesTable({
  instances,
  nativeCurrency,
  defaultCurrency,
  fxRate,
  fxState,
  onDelete,
  onRowClick,
}) {
  return (
    <>
      <div className="ec-table-wrap">
        <table className="ec-table">
          <thead>
            <tr>
              <th>Shares</th>
              <th>Avg price (native)</th>
              <th>Avg price{defaultCurrency ? ` (${defaultCurrency})` : ""}</th>
              <th>Location</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {instances.map((instance) => (
              <tr key={instance.holding.id} onClick={() => onRowClick(instance)}>
                <td>{instance.transactionsError ? "—" : instance.shares}</td>
                <td>
                  {instance.transactionsError || instance.avgPriceNative == null
                    ? "—"
                    : formatPrice(instance.avgPriceNative, nativeCurrency)}
                </td>
                <td>
                  {instance.transactionsError || instance.avgPriceNative == null
                    ? "—"
                    : fxState === "loading"
                      ? "…"
                      : fxRate != null
                        ? formatPrice(instance.avgPriceNative * fxRate, defaultCurrency)
                        : "—"}
                </td>
                <td>{instance.location}</td>
                <td>
                  <div className="ec-table-actions">
                    <button
                      type="button"
                      className="ec-icon-btn ec-icon-btn--danger"
                      aria-label={`Delete this holding in ${instance.location}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onDelete(instance);
                      }}
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
      {fxState === "unavailable" && (
        <p className="ec-holding-fx-note">
          No exchange rate is published for converting into {defaultCurrency} — showing native
          prices only.
        </p>
      )}
    </>
  );
}

export default HoldingInstancesTable;
