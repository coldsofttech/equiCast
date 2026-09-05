import { useEffect, useState } from "react";
import Button from "../../components/core/Button.jsx";
import RangeSlider from "../../components/core/RangeSlider.jsx";
import {
  MARKET_CAP_STEPS,
  indexesFromMarketCapRange,
  marketCapRangeFromIndexes,
} from "./marketCapSteps.js";
import "./SearchFilters.css";

const TYPES = [
  { value: "", label: "All types" },
  { value: "stock", label: "Stocks" },
  { value: "etf", label: "ETFs" },
  { value: "fx", label: "FX" },
];

/**
 * SearchPage's left filter pane. Type and Market cap both actually filter
 * results (mapping to the search endpoint's `asset_class`/`min_market_cap`/
 * `max_market_cap` params); Region/Exchange are shown disabled with a
 * "Coming soon" note rather than silently doing nothing — that data lives
 * on each ticker's own profile, not in the bulk catalog search results
 * (see backend/market_data/views.py's SearchView and
 * equicast_core.catalog), so there's no efficient way to filter by them
 * yet. Market cap's `market_cap` field *is* in the catalog for exactly
 * this reason.
 *
 * `type`/`minMarketCap`/`maxMarketCap` are the currently-applied filters
 * (from the URL); local `draftType`/`draftRange` let a caller change them
 * without re-searching until "Search" is clicked, same reasoning as
 * TickerSearchField not searching per keystroke — one request per explicit
 * action, not per interaction. Market cap only meaningfully narrows
 * stock/etf rows — fx always matches it regardless (see
 * MarketDataClient.search's docstring) — but the slider itself doesn't
 * call that out per-row; a fx-heavy result set simply won't visibly shrink
 * as the range tightens.
 */
function SearchFilters({ type, minMarketCap, maxMarketCap, onApply }) {
  const [draftType, setDraftType] = useState(type);
  const [draftRange, setDraftRange] = useState(() =>
    indexesFromMarketCapRange(minMarketCap, maxMarketCap)
  );

  useEffect(() => {
    setDraftType(type);
  }, [type]);

  useEffect(() => {
    setDraftRange(indexesFromMarketCapRange(minMarketCap, maxMarketCap));
  }, [minMarketCap, maxMarketCap]);

  const handleSearch = () => {
    onApply({ type: draftType, ...marketCapRangeFromIndexes(draftRange.lowIndex, draftRange.highIndex) });
  };

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

      <fieldset className="ec-search-filter-group">
        <legend>Market cap</legend>
        <RangeSlider
          steps={MARKET_CAP_STEPS}
          lowIndex={draftRange.lowIndex}
          highIndex={draftRange.highIndex}
          onChange={(lowIndex, highIndex) => setDraftRange({ lowIndex, highIndex })}
        />
        <span className="ec-search-filter-hint">Stocks by market cap, ETFs by fund size</span>
      </fieldset>

      <Button variant="primary" onClick={handleSearch}>
        Search
      </Button>
    </div>
  );
}

export default SearchFilters;
