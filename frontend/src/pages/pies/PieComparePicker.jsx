import { useEffect, useRef, useState } from "react";
import { BENCHMARKS } from "../holdings/HoldingComparePicker.jsx";
import "../holdings/HoldingComparePicker.css";

/**
 * PiePriceChart's own "Compare against" control — same collapsed-trigger /
 * open-panel / selected-chip visual states and CSS classes as
 * HoldingComparePicker, but deliberately narrower: only this account's
 * other portfolios (`pies`, already fetched by PiePriceChart) or a real
 * benchmark (the same curated set HoldingComparePicker offers as quick-
 * picks — see BENCHMARKS), never a free-text stock/ETF/fx search. A pie's
 * own list is short and already known, so the trigger opens straight to a
 * panel of buttons rather than a search box.
 *
 * A selection's `onSelect` always carries `{ id, type, refId, label }` —
 * `id` a prefixed string (`pie:<id>` / `benchmark:<key>`) suitable as the
 * caller's own state/effect-dependency key, `type` ("pie" | "benchmark")
 * and `refId` (the pie id or benchmark key) telling the caller what to
 * fetch, and `label` for display.
 *
 * @param {{ pies: { id: string, name: string }[], compareId: string, compareLabel: string|null, onSelect: (next: { id: string, type: "pie"|"benchmark", refId: string, label: string }) => void, onClear: () => void }} props
 */
function PieComparePicker({ pies, compareId, compareLabel, onSelect, onClear }) {
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

  const handleSelectPie = (pie) => {
    onSelect({ id: `pie:${pie.id}`, type: "pie", refId: pie.id, label: pie.name });
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
          {pies.length > 0 ? (
            <ul className="ec-compare-results">
              {pies.map((pie) => (
                <li key={pie.id}>
                  <button
                    type="button"
                    className="ec-compare-result"
                    onClick={() => handleSelectPie(pie)}
                  >
                    <span className="ec-compare-result-label">{pie.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="ec-compare-status">No other portfolios in this account yet.</p>
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
