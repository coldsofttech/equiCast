import { useEffect, useRef, useState } from "react";
import { BENCHMARKS } from "../holdings/HoldingComparePicker.jsx";
import "../holdings/HoldingComparePicker.css";

/**
 * PiePriceChart's own "Compare against" control (rendered from both
 * PieDetailPage and AccountDetailPage, which share that one chart
 * component — see PiePriceChart.jsx) — same collapsed-trigger / open-panel
 * / selected-chip visual states and CSS classes as HoldingComparePicker,
 * but deliberately narrower: only `items`
 * (this pie's sibling portfolios, or this account's sibling accounts —
 * already fetched by the caller) or a real benchmark (the same curated set
 * HoldingComparePicker offers as quick-picks — see BENCHMARKS), never a
 * free-text stock/ETF/fx search. `items` is always short and already
 * known, so the trigger opens straight to a panel of buttons rather than a
 * search box.
 *
 * A selection's `onSelect` always carries `{ id, type, refId, label }` —
 * `id` a prefixed string (`${itemType}:<id>` / `benchmark:<key>`) suitable
 * as the caller's own state/effect-dependency key, `type` (`itemType` as
 * given, or `"benchmark"`) and `refId` (the item's id or benchmark key)
 * telling the caller what to fetch, and `label` for display.
 *
 * @param {{ items: { id: string, name: string }[], itemType?: "pie"|"account", compareId: string, compareLabel: string|null, onSelect: (next: { id: string, type: string, refId: string, label: string }) => void, onClear: () => void }} props
 */
function PieComparePicker({ items, itemType = "pie", compareId, compareLabel, onSelect, onClear }) {
  const rootRef = useRef(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handlePointerDown = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (event) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const handleSelectItem = (item) => {
    onSelect({ id: `${itemType}:${item.id}`, type: itemType, refId: item.id, label: item.name });
    setIsOpen(false);
  };

  const handleSelectBenchmark = (benchmark) => {
    onSelect({ id: `benchmark:${benchmark.key}`, type: "benchmark", refId: benchmark.key, label: benchmark.name });
    setIsOpen(false);
  };

  if (compareId) {
    return (
      <div className="ec-compare-chip">
        <span className="ec-compare-chip-label">{compareLabel}</span>
        <button
          type="button"
          className="ec-compare-chip-clear"
          onClick={onClear}
          aria-label="Clear comparison"
        >
          <i className="bi bi-x-lg" aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <div className="ec-compare-picker" ref={rootRef}>
      <button
        type="button"
        className="ec-compare-search"
        onClick={() => setIsOpen((open) => !open)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
      >
        <i className="bi bi-search" aria-hidden="true" />
        <span className="ec-compare-search-placeholder">Compare against…</span>
      </button>

      {isOpen && (
        <div className="ec-compare-panel" role="listbox">
          {items.length > 0 ? (
            <ul className="ec-compare-results">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="ec-compare-result"
                    onClick={() => handleSelectItem(item)}
                  >
                    <span className="ec-compare-result-label">{item.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="ec-compare-status">
              {itemType === "account" ? "No other accounts yet." : "No other portfolios in this account yet."}
            </p>
          )}

          <div className="ec-compare-benchmarks">
            <p className="ec-compare-benchmarks-label">Benchmarks</p>
            <div className="ec-compare-benchmarks-row">
              {BENCHMARKS.map((benchmark) => (
                <button
                  key={benchmark.key}
                  type="button"
                  className="ec-compare-benchmark-btn"
                  onClick={() => handleSelectBenchmark(benchmark)}
                >
                  {benchmark.name}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PieComparePicker;
