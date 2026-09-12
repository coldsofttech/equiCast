import { useState } from "react";
import Card from "../../components/core/Card.jsx";
import { SelectField, TextField } from "../../components/core/Field.jsx";
import Button from "../../components/core/Button.jsx";
import Alert from "../../components/core/Alert.jsx";
import TickerSearchField from "../pies/TickerSearchField.jsx";
import { useApi } from "../../api/useApi.js";
import { commitImport } from "../../api/transactions.js";
import "./ImportPage.css";

/** `{type, id}` -> the `value` a target `<select>` option/selection uses —
 * a plain string since native `<select>` values are always strings. */
function targetKey(type, id) {
  return `${type}:${id}`;
}

function buildInitialSelection(group) {
  const firstExisting = group.existing_holdings[0];
  return {
    include: group.resolved,
    ticker: group.ticker,
    assetClass: group.asset_class,
    targetType: firstExisting ? "existing_holding" : "account",
    targetId: firstExisting ? firstExisting.id : "",
    allocationPct: "",
  };
}

/** Every account/pie the user could import a *new* holding into, flattened
 * from `listAccounts`' nested shape — an existing-holding target (when a
 * group already matches one) is offered separately, from the group itself,
 * since that's specific to the ticker rather than every account/pie. */
function flattenNewHoldingTargets(accounts) {
  const targets = [];
  for (const account of accounts) {
    targets.push({ type: "account", id: account.id, label: account.name });
    for (const pie of account.pies ?? []) {
      targets.push({ type: "pie", id: pie.id, label: `${account.name} → ${pie.name}` });
    }
  }
  return targets;
}

/**
 * Second wizard step: per ticker group, let the user include/exclude it,
 * remap an unresolved ticker (`TickerSearchField`), pick a target
 * account/pie/existing holding (and an allocation % for a non-empty pie),
 * then `commitImport` — see backend/transactions/import_views.py's
 * ImportCommitView. Selection is per *holding* (group), not per row — every
 * row in an included group is sent; TRANSACTION-mode duplicates and
 * AVERAGE-mode "already has a position" are resolved server-side (see
 * each group's badges below) rather than requiring the user to hand-pick
 * rows.
 */
function ImportReviewStep({ preview, accounts, onBack, onCommitted, onCancel }) {
  const api = useApi();
  const [selections, setSelections] = useState(() =>
    Object.fromEntries(preview.groups.map((group) => [group.ticker, buildInitialSelection(group)]))
  );
  const [error, setError] = useState(null);
  const [isCommitting, setIsCommitting] = useState(false);

  const targets = flattenNewHoldingTargets(accounts);

  const updateSelection = (ticker, patch) => {
    setSelections((current) => ({ ...current, [ticker]: { ...current[ticker], ...patch } }));
  };

  const handleRemap = (ticker, result) => {
    updateSelection(ticker, {
      include: true,
      ticker: result.ticker,
      assetClass: result.asset_class,
    });
  };

  const handleTargetChange = (ticker, value) => {
    const [targetType, targetId] = value.split(":");
    updateSelection(ticker, { targetType, targetId, allocationPct: "" });
  };

  const handleCommit = () => {
    const payload = preview.groups
      .map((group) => ({ group, selection: selections[group.ticker] }))
      .filter(({ selection }) => selection.include)
      .map(({ group, selection }) => ({
        ticker: selection.ticker,
        asset_class: selection.assetClass,
        target: {
          type: selection.targetType,
          id: selection.targetId,
          ...(selection.targetType === "pie" && selection.allocationPct
            ? { allocation_pct: Number(selection.allocationPct) }
            : {}),
        },
        rows: group.rows,
      }));

    if (payload.length === 0) {
      setError("Select at least one holding to import.");
      return;
    }
    if (payload.some((selection) => !selection.target.id)) {
      setError("Choose where to import every selected holding.");
      return;
    }

    setIsCommitting(true);
    setError(null);
    commitImport(api, payload)
      .then((response) => onCommitted(response.results))
      .catch((err) => setError(err.message ?? "Import failed."))
      .finally(() => setIsCommitting(false));
  };

  return (
    <div className="ec-form ec-import-step">
      {error && <Alert tone="danger">{error}</Alert>}
      {preview.rows_skipped > 0 && (
        <Alert tone="info">
          {preview.rows_skipped} row(s) in the file weren&rsquo;t buy/sell orders (dividends,
          interest, ...) and were ignored.
        </Alert>
      )}

      <div className="ec-import-groups">
        {preview.groups.map((group) => {
          const selection = selections[group.ticker];
          const canInclude = Boolean(selection.assetClass);

          return (
            <Card key={group.ticker} className="ec-import-group">
              <label className="ec-import-group-header">
                <input
                  type="checkbox"
                  checked={selection.include}
                  disabled={!canInclude}
                  onChange={() =>
                    updateSelection(group.ticker, { include: !selection.include })
                  }
                />
                <span className="ec-import-group-ticker">{selection.ticker}</span>
                {group.name && <span className="ec-import-group-name">{group.name}</span>}
                <span className="ec-import-group-rows-count">{group.rows.length} row(s)</span>
              </label>

              {!canInclude && (
                <div className="ec-import-group-remap">
                  <Alert tone="danger">
                    Couldn&rsquo;t match &ldquo;{group.ticker}&rdquo; to equicast&rsquo;s catalog —
                    search for the right one to include it:
                  </Alert>
                  <TickerSearchField onSelect={(result) => handleRemap(group.ticker, result)} />
                </div>
              )}

              {selection.include && (
                <div className="ec-import-group-body">
                  {group.mode_preview && (
                    <p className="ec-import-group-summary">
                      Net {group.mode_preview.no_of_shares} share(s)
                      {group.mode_preview.average_price_native != null &&
                        ` @ avg ${group.mode_preview.average_price_native.toFixed(2)}`}
                    </p>
                  )}

                  <SelectField
                    id={`import-target-${group.ticker}`}
                    label="Import into"
                    value={targetKey(selection.targetType, selection.targetId)}
                    onChange={(event) => handleTargetChange(group.ticker, event.target.value)}
                  >
                    {group.existing_holdings.map((holding) => (
                      <option
                        key={holding.id}
                        value={targetKey("existing_holding", holding.id)}
                      >
                        {holding.account_name ?? "Pie holding"} — existing
                        {holding.already_has_position ? ", will extend position" : ""}
                        {holding.duplicate_count > 0
                          ? `, ${holding.duplicate_count} row(s) already imported`
                          : ""}
                      </option>
                    ))}
                    <option value="" disabled>
                      — new holding in —
                    </option>
                    {targets.map((target) => (
                      <option key={targetKey(target.type, target.id)} value={targetKey(target.type, target.id)}>
                        {target.label}
                      </option>
                    ))}
                  </SelectField>

                  {selection.targetType === "pie" && (
                    <TextField
                      id={`import-allocation-${group.ticker}`}
                      label="Allocation % in this pie"
                      type="number"
                      min="0.01"
                      max="100"
                      step="0.01"
                      value={selection.allocationPct}
                      onChange={(event) =>
                        updateSelection(group.ticker, { allocationPct: event.target.value })
                      }
                      hint="Leave blank if this pie has no holdings yet — it becomes 100% automatically."
                    />
                  )}
                </div>
              )}
            </Card>
          );
        })}
      </div>

      <div className="ec-form-actions">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={isCommitting}>
          Cancel
        </Button>
        <Button type="button" variant="secondary" onClick={onBack} disabled={isCommitting}>
          Back
        </Button>
        <Button type="button" variant="primary" isLoading={isCommitting} onClick={handleCommit}>
          Import
        </Button>
      </div>
    </div>
  );
}

export default ImportReviewStep;
