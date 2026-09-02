import { useEffect, useState } from "react";
import Button from "../../components/core/Button.jsx";
import Badge from "../../components/core/Badge.jsx";
import Alert from "../../components/core/Alert.jsx";
import "./AllocationEditor.css";

const ASSET_CLASSES = ["stock", "etf", "fx"];

let nextTempKey = 0;

function holdingsToRows(holdings) {
  return holdings.map((holding) => ({
    key: holding.id,
    id: holding.id,
    ticker: holding.ticker,
    asset_class: holding.asset_class,
    allocation_pct: String(holding.allocation_pct),
    removed: false,
  }));
}

function blankRow() {
  return {
    key: `new-${nextTempKey++}`,
    id: undefined,
    ticker: "",
    asset_class: "stock",
    allocation_pct: "",
    removed: false,
  };
}

/**
 * The add/remove/reallocate batch editor for one pie's holdings — the
 * only way to mutate them (see backend/pies/views.py's PieHoldingsView.put
 * and equicast_core.holdings.sync_pie_holdings). Local `rows` state tracks
 * every existing holding plus any newly-added blank rows; `removed` marks
 * an existing row for the `remove` list rather than splicing it out
 * immediately, so its allocation still counts toward "what the total would
 * be if you saved this" — a freshly-added row IS spliced out on remove
 * since it was never real to begin with.
 *
 * `holdings` resets local edits whenever it changes (a fresh load, or the
 * parent replacing it with the server's post-save state) — mid-edit,
 * PieDetailPage only updates it on those two occasions, so this doesn't
 * clobber in-progress typing.
 */
function AllocationEditor({ holdings, onSave, isSaving, error }) {
  const [rows, setRows] = useState(() => holdingsToRows(holdings));

  useEffect(() => {
    setRows(holdingsToRows(holdings));
  }, [holdings]);

  const updateRow = (key, field, value) =>
    setRows((current) => current.map((row) => (row.key === key ? { ...row, [field]: value } : row)));

  const removeRow = (key) =>
    setRows((current) =>
      current
        .map((row) => (row.key === key ? { ...row, removed: true } : row))
        .filter((row) => row.id || !row.removed)
    );

  const addRow = () => setRows((current) => [...current, blankRow()]);

  const activeRows = rows.filter((row) => !row.removed);
  const total = activeRows.reduce((sum, row) => sum + (parseFloat(row.allocation_pct) || 0), 0);
  const totalTone = activeRows.length === 0 ? "neutral" : total === 100 ? "success" : "warning";

  const hasInvalidRow = activeRows.some(
    (row) => !row.ticker.trim() || !row.allocation_pct.trim() || Number(row.allocation_pct) <= 0
  );
  const isDirty =
    rows.some((row) => row.removed && row.id) ||
    activeRows.some((row) => !row.id) ||
    activeRows.some((row) => {
      const original = holdings.find((h) => h.id === row.id);
      return original && String(original.allocation_pct) !== row.allocation_pct;
    });

  const handleSave = () => {
    const remove = rows.filter((row) => row.removed && row.id).map((row) => row.id);
    const add = activeRows
      .filter((row) => !row.id)
      .map((row) => ({
        ticker: row.ticker.trim().toUpperCase(),
        asset_class: row.asset_class,
        allocation_pct: row.allocation_pct,
      }));
    const reallocate = activeRows
      .filter((row) => {
        if (!row.id) return false;
        const original = holdings.find((h) => h.id === row.id);
        return original && String(original.allocation_pct) !== row.allocation_pct;
      })
      .map((row) => ({ id: row.id, allocation_pct: row.allocation_pct }));

    onSave({ add, remove, reallocate });
  };

  return (
    <div className="ec-allocation-editor">
      {error && <Alert tone="danger">{error}</Alert>}

      {activeRows.length === 0 ? (
        <p className="ec-allocation-empty">No holdings yet — add one below.</p>
      ) : (
        <div className="ec-allocation-table">
          <div className="ec-allocation-row ec-allocation-header">
            <span>Ticker</span>
            <span>Asset class</span>
            <span>Allocation %</span>
            <span />
          </div>
          {rows
            .filter((row) => !row.removed)
            .map((row) => (
              <div className="ec-allocation-row" key={row.key}>
                <input
                  className="ec-input"
                  value={row.ticker}
                  placeholder="AAPL"
                  disabled={Boolean(row.id)}
                  onChange={(event) => updateRow(row.key, "ticker", event.target.value)}
                  aria-label="Ticker"
                />
                <select
                  className="ec-select"
                  value={row.asset_class}
                  disabled={Boolean(row.id)}
                  onChange={(event) => updateRow(row.key, "asset_class", event.target.value)}
                  aria-label="Asset class"
                >
                  {ASSET_CLASSES.map((assetClass) => (
                    <option key={assetClass} value={assetClass}>
                      {assetClass}
                    </option>
                  ))}
                </select>
                <input
                  className="ec-input"
                  value={row.allocation_pct}
                  placeholder="0"
                  inputMode="decimal"
                  onChange={(event) => updateRow(row.key, "allocation_pct", event.target.value)}
                  aria-label="Allocation percent"
                />
                <Button variant="ghost" size="sm" onClick={() => removeRow(row.key)}>
                  Remove
                </Button>
              </div>
            ))}
        </div>
      )}

      <div className="ec-allocation-footer">
        <Button variant="secondary" size="sm" onClick={addRow}>
          Add holding
        </Button>
        <div className="ec-allocation-total">
          <span>Total</span>
          <Badge tone={totalTone}>{total}%</Badge>
        </div>
      </div>

      <div className="ec-form-actions">
        <Button
          variant="primary"
          onClick={handleSave}
          isLoading={isSaving}
          disabled={!isDirty || hasInvalidRow || (activeRows.length > 0 && total !== 100)}
        >
          Save changes
        </Button>
      </div>
    </div>
  );
}

export default AllocationEditor;
