import { useEffect, useRef, useState } from "react";
import AssetTypeBadge from "../../components/core/AssetTypeBadge.jsx";
import { useApi } from "../../api/useApi.js";
import { searchTickers } from "../../api/market.js";
import "./HoldingComparePicker.css";

/** Quick-pick benchmarks — real `equicast-benchmark` keys (see
 * packages/benchmark/config/benchmarks.*.yaml). Deliberately every one of
 * benchmarks.dev.yaml's 5 keys (a subset of prod's 15 by design), so this
 * quick-pick always resolves in both environments rather than 404ing
 * locally for a prod-only benchmark. Anything not listed here is still
 * reachable through the search box above (assetClass: "benchmark").
 * Exported so PiePriceChart's own (simpler, no free-text search) "Compare
 * against" select can offer the same real benchmark set without
 * duplicating it. */
export const BENCHMARKS = [
  { key: "SP500", name: "S&P 500" },
  { key: "FTSE100", name: "FTSE 100" },
  { key: "MSCI_WORLD", name: "MSCI World" },
  { key: "DAX", name: "DAX" },
  { key: "STOXX_EUROPE_600", name: "STOXX Europe 600" },
];

/** How many search matches to show — enough to be useful in a compact
 * toolbar dropdown without turning into a full results page. */
const RESULT_LIMIT = 8;

/**
 * HoldingPriceChart's "Compare against" control. Searches the app's full
 * stock/ETF/benchmark catalog (GET /market/search/ — same endpoint
 * SearchPage and TickerSearchField use for stock/etf; benchmark is
 * explicitly opt-in there, see api/market.js's searchTickers docstring)
 * rather than only tickers the user already owns, so e.g. an AVGO page can
 * compare against AAPL, VOO, or the S&P 500 whether or not they're
 * actually held. FX is excluded — a price overlay against a currency pair
 * isn't a meaningful comparison — by querying "stock"/"etf"/"benchmark"
 * separately and merging, since the search endpoint only accepts one
 * asset_class filter at a time. Search runs on Enter, not per keystroke,
 * matching TickerSearchField's one-call-per-lookup convention; the
 * dropdown panel and outside-click/Escape-to-close behavior mirror
 * TopbarSearch.
 *
 * A curated set of benchmarks also stays a quick-pick list inside the same
 * panel (see BENCHMARKS above) — real `equicast-benchmark` keys, not a
 * placeholder; anything not in that short list is still reachable by
 * typing its name/ticker into the search box.
 *
 * Once something is selected, the control collapses to a chip (matching
 * the account/pie chart's plain "Compare against…" select's spirit of
 * showing one active comparison at a time) with a clear button that
 * restores the search box.
 *
 * A selection's `onSelect` always includes a real `ticker`/`assetClass` —
 * a search result's own, or a quick-pick benchmark's `key`/`"benchmark"` —
 * so the caller (HoldingPriceChart) can fetch that symbol's own real price
 * series via the same GET .../prices/ call (and same IndexedDB cache) it
 * uses for its main subject.
 *
 * @param {{ currentTicker: string, compareId: string, compareLabel: string|null, onSelect: (next: { compareId: string, label: string, ticker: string, assetClass: string }) => void, onClear: () => void }} props
 */
function HoldingComparePicker({ currentTicker, compareId, compareLabel, onSelect, onClear }) {
  const api = useApi();
  const rootRef = useRef(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState(null);
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

  const runSearch = () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setIsSearching(true);
    setError(null);
    Promise.all([
      searchTickers(api, trimmed, { assetClass: "stock", pageSize: RESULT_LIMIT }),
      searchTickers(api, trimmed, { assetClass: "etf", pageSize: RESULT_LIMIT }),
      searchTickers(api, trimmed, { assetClass: "benchmark", pageSize: RESULT_LIMIT }),
    ])
      .then(([stocks, etfs, benchmarks]) => {
        const matches = [...stocks.results, ...etfs.results, ...benchmarks.results]
          .filter((result) => result.ticker.toUpperCase() !== currentTicker.toUpperCase())
          .slice(0, RESULT_LIMIT);
        setResults(matches);
      })
      .catch((err) => {
        setError(err.message ?? "Search failed.");
        setResults(null);
      })
      .finally(() => setIsSearching(false));
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runSearch();
    }
  };

  const handleSelectTicker = (result) => {
    onSelect({
      compareId: `holding:${result.ticker}`,
      label: result.name || result.ticker,
      ticker: result.ticker,
      assetClass: result.type,
    });
    setQuery("");
    setResults(null);
    setIsOpen(false);
  };

  const handleSelectBenchmark = (benchmark) => {
    onSelect({
      compareId: `benchmark:${benchmark.key}`,
      label: benchmark.name,
      ticker: benchmark.key,
      assetClass: "benchmark",
    });
    setQuery("");
    setResults(null);
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
      <div className="ec-compare-search">
        <i className="bi bi-search" aria-hidden="true" />
        <input
          type="search"
          className="ec-compare-search-input"
          placeholder="Compare against a stock, ETF, or benchmark…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setIsOpen(true)}
          aria-label="Compare against a stock, ETF, or benchmark"
        />
      </div>

      {isOpen && (
        <div className="ec-compare-panel" role="listbox">
          {isSearching ? (
            <p className="ec-compare-status">Searching…</p>
          ) : error ? (
            <p className="ec-compare-status ec-compare-status--error">{error}</p>
          ) : results && results.length === 0 ? (
            <p className="ec-compare-status">
              No stocks, ETFs, or benchmarks matched &ldquo;{query.trim()}&rdquo;.
            </p>
          ) : (
            results && (
              <ul className="ec-compare-results">
                {results.map((result) => (
                  <li key={`${result.type}:${result.ticker}`}>
                    <button
                      type="button"
                      className="ec-compare-result"
                      onClick={() => handleSelectTicker(result)}
                    >
                      <span className="ec-compare-result-ticker">{result.ticker}</span>
                      <span className="ec-compare-result-name">{result.name}</span>
                      <AssetTypeBadge type={result.type} />
                    </button>
                  </li>
                ))}
              </ul>
            )
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

export default HoldingComparePicker;
