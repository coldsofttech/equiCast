import { useEffect, useState } from "react";
import Button from "../../components/core/Button.jsx";
import Badge from "../../components/core/Badge.jsx";
import Alert from "../../components/core/Alert.jsx";
import TickerSearchField from "./TickerSearchField.jsx";
import "./AllocationEditor.css";

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

/**
 * A small ring showing progress toward 100% allocation — green at exactly
 * 100%, red once over, amber otherwise. Visually clamped at a full circle
 * past 100% (the color communicates "over", not an impossible >360° arc).
 */
function AllocationRing({ pct }) {
  const clamped = Math.min(Math.max(pct, 0), 100);
  const radius = 15;
  const circumference = 2 * Math.PI * radius;
  const dash = (clamped / 100) * circumference;
  const tone =
    pct > 100 ? "var(--ec-danger)" : pct === 100 ? "var(--ec-success)" : "var(--ec-warning)";

  return (
    <svg
      width="36"
      height="36"
      viewBox="0 0 36 36"
      className="ec-allocation-ring"
      role="img"
      aria-label={`${pct}% allocated${pct > 100 ? ", over 100%" : ""}`}
    >
      <circle cx="18" cy="18" r={radius} fill="none" stroke="var(--ec-surface-2)" strokeWidth="4" />
      <circle
        cx="18"
        cy="18"
        r={radius}
        fill="none"
        stroke={tone}
        strokeWidth="4"
        strokeDasharray={`${dash} ${circumference}`}
        strokeLinecap="round"
        transform="rotate(-90 18 18)"
      />
    </svg>
  );
}

/**
 * The add/remove/reallocate batch editor for one pie's holdings — the
 * only way to mutate them (see backend/pies/views.py's PieHoldingsView.put
 * and equicast_core.holdings.sync_pie_holdings). Ticker/asset_class are
 * always picked via TickerSearchField (the real catalog search), never
 * typed by hand — every row's ticker is fixed once added; only its
 * allocation % stays editable. Local `rows` state tracks every existing
 * holding plus any newly-added rows; `removed` marks an existing row for
 * the `remove` list rather than splicing it out immediately, so its
 * allocation still counts toward "what the total would be if you saved
 * this" — a freshly-added row IS spliced out on remove since it was never
 * real to begin with.
 *
 * `holdings` resets local edits whenever it changes (a fresh load, or the
 * caller replacing it with the server's post-save state) — mid-edit, the
 * caller only updates it on those two occasions, so this doesn't clobber
 * in-progress typing.
 */
function AllocationEditor({ holdings, onSave, isSaving, error }) {
  const [rows, setRows] = useState(() => holdingsToRows(holdings));
  const [duplicateError, setDuplicateError] = useState(null);

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

  const activeRows = rows.filter((row) => !row.removed);

  const handleTickerSelected = ({ ticker, asset_class }) => {
    if (activeRows.some((row) => row.ticker === ticker)) {
      setDuplicateError(`${ticker} is already in this pie.`);
      return;
    }
    setDuplicateError(null);
    setRows((current) => [
      ...current,
      {
        key: `new-${nextTempKey++}`,
        id: undefined,
        ticker,
        asset_class,
        allocation_pct: "",
        removed: false,
      },
    ]);
  };

  const total = activeRows.reduce((sum, row) => sum + (parseFloat(row.allocation_pct) || 0), 0);
  const totalTone =
    activeRows.length === 0 ? "neutral" : total === 100 ? "success" : total > 100 ? "danger" : "warning";

  const hasInvalidRow = activeRows.some(
    (row) => !row.allocation_pct.trim() || Number(row.allocation_pct) <= 0
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
        ticker: row.ticker,
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

      <div className="ec-allocation-summary">
        <AllocationRing pct={total} />
        <div className="ec-allocation-summary-text">
          <span className="ec-allocation-total-label">Total allocated</span>
          <Badge tone={totalTone}>{total}%</Badge>
        </div>
      </div>

      {activeRows.length === 0 ? (
        <p className="ec-allocation-empty">No holdings yet — search below to add one.</p>
      ) : (
        <div className="ec-allocation-table">
          <div className="ec-allocation-row ec-allocation-header">
            <span>Ticker</span>
            <span>Asset class</span>
            <span>Allocation %</span>
            <span />
          </div>
          {activeRows.map((row) => (
            <div className="ec-allocation-row" key={row.key}>
              <span className="ec-allocation-ticker">{row.ticker}</span>
              <Badge tone="neutral">{row.asset_class}</Badge>
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

      <div className="ec-allocation-add">
        {duplicateError && (
          <p className="ec-ticker-search-error" role="alert">
            {duplicateError}
          </p>
        )}
        <TickerSearchField onSelect={handleTickerSelected} />
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
