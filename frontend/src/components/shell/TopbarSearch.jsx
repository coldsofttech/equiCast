import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import AssetIcon from "../core/AssetIcon.jsx";
import AssetTypeBadge from "../core/AssetTypeBadge.jsx";
import { useApi } from "../../api/useApi.js";
import { searchTickers } from "../../api/market.js";
import "./TopbarSearch.css";

/** How many rows the preview dropdown shows before "More results" — enough
 * to be useful without turning the topbar into a full results page; the
 * real paging/filtering lives on SearchPage. */
const PREVIEW_SIZE = 7;

/**
 * The topbar's ticker/company search box. Enter runs one search (never per
 * keystroke — see TickerSearchField.jsx for why) and opens a preview
 * dropdown of up to PREVIEW_SIZE matches; "More results" in that dropdown
 * is the only thing that navigates to /search?q=..., where SearchPage owns
 * paging/filtering the same query further.
 */
function TopbarSearch() {
  const navigate = useNavigate();
  const api = useApi();
  const rootRef = useRef(null);

  const [value, setValue] = useState("");
  const [results, setResults] = useState(null);
  const [count, setCount] = useState(0);
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

  const runSearch = (trimmed) => {
    setIsSearching(true);
    setError(null);
    searchTickers(api, trimmed, { pageSize: PREVIEW_SIZE })
      .then((response) => {
        setResults(response.results);
        setCount(response.count);
        setIsOpen(true);
      })
      .catch((err) => {
        setError(err.message ?? "Search failed.");
        setResults(null);
        setIsOpen(true);
      })
      .finally(() => setIsSearching(false));
  };

  const handleKeyDown = (event) => {
    if (event.key !== "Enter") return;
    const trimmed = value.trim();
    if (!trimmed) return;
    runSearch(trimmed);
  };

  const handleMoreResults = () => {
    setIsOpen(false);
    navigate(`/search?q=${encodeURIComponent(value.trim())}`);
  };

  return (
    <div className="ec-topbar-search-wrap" ref={rootRef}>
      <div className="ec-topbar-search">
        <i className="bi bi-search" aria-hidden="true" />
        <input
          type="search"
          className="ec-topbar-search-input"
          placeholder="Search tickers…"
          value={value}
          onChange={(event) => {
            setValue(event.target.value);
            if (!event.target.value.trim()) setIsOpen(false);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => {
            if (results !== null || error) setIsOpen(true);
          }}
          aria-label="Search tickers"
        />
      </div>

      {isOpen && (
        <div className="ec-topbar-search-panel" role="listbox">
          {isSearching ? (
            <p className="ec-topbar-search-status">Searching…</p>
          ) : error ? (
            <p className="ec-topbar-search-status ec-topbar-search-status--error">{error}</p>
          ) : results && results.length === 0 ? (
            <p className="ec-topbar-search-status">No matches for &ldquo;{value.trim()}&rdquo;.</p>
          ) : (
            results && (
              <>
                <ul className="ec-topbar-search-results">
                  {results.map((result) => (
                    <li key={`${result.type}:${result.ticker}`}>
                      <div className="ec-topbar-search-result">
                        <AssetIcon website={result.website} size={16} />
                        <span className="ec-topbar-search-result-ticker">{result.ticker}</span>
                        <span className="ec-topbar-search-result-name">{result.name}</span>
                        <AssetTypeBadge type={result.type} />
                      </div>
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  className="ec-topbar-search-more"
                  onClick={handleMoreResults}
                >
                  More results{count > results.length ? ` (${count})` : ""}
                </button>
              </>
            )
          )}
        </div>
      )}
    </div>
  );
}

export default TopbarSearch;
