import { useEffect, useState } from "react";
import Button from "../../components/core/Button.jsx";
import "./SearchFilters.css";

const TYPES = [
  { value: "", label: "All types" },
  { value: "stock", label: "Stocks" },
  { value: "etf", label: "ETFs" },
  { value: "fx", label: "FX" },
];

/**
 * SearchPage's left filter pane. Only Type actually filters results — it
 * maps to the search endpoint's `asset_class` param. Region/Exchange/
 * Market cap are shown disabled with a "Coming soon" note rather than
 * silently doing nothing: the catalog search index only carries ticker/
 * name/type/current_price today (see backend/market_data/views.py's
 * SearchView and equicast_core.catalog) — those other fields live on each
 * ticker's own profile, not in the bulk search results, so there's no
 * efficient way to filter by them yet.
 *
 * `type` is the currently-applied filter (from the URL); local `draftType`
 * lets a caller change the radio without re-searching until "Search" is
 * clicked, same reasoning as TickerSearchField not searching per keystroke
 * — one request per explicit action, not per interaction.
 */
function SearchFilters({ type, onApply }) {
  const [draftType, setDraftType] = useState(type);

  useEffect(() => {
    setDraftType(type);
  }, [type]);

  return (
    <div className="ec-search-filters">
      <fieldset className="ec-search-filter-group">
        <legend>Type</legend>
        {TYPES.map((option) => (
          <label key={option.value || "all"} className="ec-search-filter-option">
            <input
              type="radio"
              name="search-type"
              value={option.value}
              checked={draftType === option.value}
              onChange={() => setDraftType(option.value)}
            />
            {option.label}
          </label>
        ))}
      </fieldset>

      <fieldset className="ec-search-filter-group" disabled>
        <legend>Region</legend>
        <select className="ec-select" disabled defaultValue="">
          <option value="">All regions</option>
        </select>
        <span className="ec-search-filter-soon">Coming soon</span>
      </fieldset>

      <fieldset className="ec-search-filter-group" disabled>
        <legend>Exchange</legend>
        <select className="ec-select" disabled defaultValue="">
          <option value="">All exchanges</option>
        </select>
        <span className="ec-search-filter-soon">Coming soon</span>
      </fieldset>

      <fieldset className="ec-search-filter-group" disabled>
        <legend>Market cap</legend>
        <select className="ec-select" disabled defaultValue="">
          <option value="">Any market cap</option>
        </select>
        <span className="ec-search-filter-soon">Coming soon</span>
      </fieldset>

      <Button variant="primary" onClick={() => onApply(draftType)}>
        Search
      </Button>
    </div>
  );
}

export default SearchFilters;
