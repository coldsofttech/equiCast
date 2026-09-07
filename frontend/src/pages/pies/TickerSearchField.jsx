import { useState } from "react";
import AssetIcon from "../../components/core/AssetIcon.jsx";
import AssetTypeBadge from "../../components/core/AssetTypeBadge.jsx";
import { useApi } from "../../api/useApi.js";
import { searchTickers } from "../../api/market.js";
import "./TickerSearchField.css";

/**
 * A ticker search box for adding a holding to a pie — searches only on
 * Enter, never per keystroke, to keep this to one API call per lookup
 * against the real catalog search (backend/market_data/views.py's
 * SearchView) rather than one per character. Styled like TopbarSearch (a
 * plain search icon inside the input, no separate button). Picking a
 * result calls `onSelect({ ticker, asset_class, name, website })` and
 * resets the field.
 */
function TickerSearchField({ onSelect }) {
  const api = useApi();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState(null);

  const runSearch = () => {
    const trimmed = query.trim();
    if (!trimmed) return;
    setIsSearching(true);
    setError(null);
    searchTickers(api, trimmed)
      .then((response) => setResults(response.results))
      .catch((err) => setError(err.message ?? "Search failed."))
      .finally(() => setIsSearching(false));
  };

  const handleSelect = (result) => {
    onSelect({
      ticker: result.ticker,
      asset_class: result.type,
      name: result.name,
      website: result.website,
    });
    setQuery("");
    setResults(null);
  };

  return (
    <div className="ec-ticker-search">
      <div className="ec-ticker-search-input-wrap">
        <i className="bi bi-search" aria-hidden="true" />
        <input
          type="search"
          className="ec-ticker-search-input"
          value={query}
          placeholder="Search ticker or name, then press Enter…"
          onChange={(event) => {
            setQuery(event.target.value);
            setResults(null);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              runSearch();
            }
          }}
          aria-label="Search ticker or name"
        />
      </div>

      {isSearching && <p className="ec-ticker-search-status">Searching…</p>}

      {error && (
        <p className="ec-ticker-search-error" role="alert">
          {error}
        </p>
      )}

      {results &&
        (results.length === 0 ? (
          <p className="ec-ticker-search-empty">No matches for &ldquo;{query}&rdquo;.</p>
        ) : (
          <ul className="ec-ticker-search-results">
            {results.map((result) => (
              <li key={`${result.type}:${result.ticker}`}>
                <button
                  type="button"
                  className="ec-ticker-search-result"
                  onClick={() => handleSelect(result)}
                >
                  <AssetIcon website={result.website} size={16} />
                  <span className="ec-ticker-search-result-ticker">{result.ticker}</span>
                  <span className="ec-ticker-search-result-name">{result.name}</span>
                  <AssetTypeBadge type={result.type} />
                </button>
              </li>
            ))}
          </ul>
        ))}
    </div>
  );
}

export default TickerSearchField;
