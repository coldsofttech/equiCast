import { useEffect, useState } from "react";
import Button from "../../components/core/Button.jsx";
import RangeSlider from "../../components/core/RangeSlider.jsx";
import {
  MARKET_CAP_MAX_INDEX,
  MARKET_CAP_MIN_INDEX,
  MARKET_CAP_STEPS,
  indexesFromMarketCapRange,
  marketCapRangeFromIndexes,
} from "./marketCapSteps.js";
import {
  EXCHANGE_OPTIONS,
  INDUSTRY_OPTIONS,
  REGION_OPTIONS,
  SECTOR_OPTIONS,
} from "./searchFilterOptions.js";
import "./SearchFilters.css";

const TYPES = [
  { value: "", label: "All types" },
  { value: "stock", label: "Stocks" },
  { value: "etf", label: "ETFs" },
  { value: "fx", label: "FX" },
  { value: "future", label: "Futures" },
];

/**
 * SearchPage's left filter pane. Keyword, Type, Market cap, Region,
 * Exchange, Sector and Industry all actually filter results now (mapping
 * to the search endpoint's `q`/`asset_class`/`min_market_cap`/
 * `max_market_cap`/`region`/`exchange`/`sector`/`industry` params) —
 * Region/Exchange/Sector/Industry's option lists are static config
 * (searchFilterOptions.js) rather than derived from the catalog, since
 * equiCast's ticker list is presently hand-picked from a small fixed set.
 * Type/Market cap/Region/Exchange only meaningfully narrow stock/etf rows,
 * and Sector/Industry only stock rows — fx always matches every one of
 * them regardless (see MarketDataClient.search's docstring) — but none of
 * the controls call that out per-row; a fx-heavy result set simply won't
 * visibly shrink as they tighten. "Futures" (`type: "future"`, added
 * alongside Stocks/ETFs/FX — unlike "Benchmark", which is deliberately
 * never offered here, only reachable via HoldingComparePicker's own
 * explicit search) behaves differently from fx: a future row has none of
 * Market cap/Region/Sector/Industry's concepts (always `None` in its
 * catalog row), so it's *excluded* whenever any of those is applied,
 * rather than always matching like fx — only Exchange narrows it
 * meaningfully, since yfinance does report one for a futures contract.
 * Leaving Market cap/Region/Sector/Industry at their defaults is what
 * keeps a Type: Futures search populated.
 *
 * `query`/`type`/`minMarketCap`/`maxMarketCap`/`region`/`exchange`/
 * `sector`/`industry` are the currently-applied filters (from the URL —
 * `query` is whatever the topbar search box was last submitted with);
 * local `draftQuery`/`draftType`/`draftRange`/`draftRegion`/
 * `draftExchange`/`draftSector`/`draftIndustry` let a caller change them
 * without re-searching until "Search" is clicked (or Enter is pressed in
 * the Keyword field), same reasoning as TickerSearchField not searching per
 * keystroke — one request per explicit action, not per interaction. The
 * header's Clear icon is the one exception — it resets every draft
 * (Keyword included) to its default *and* applies immediately, rather than
 * waiting for a separate "Search" click, since a reset with no visible
 * effect until another click would confuse a user pressing it expecting an
 * unfiltered result set right away; it's disabled once every draft is
 * already at its default.
 */
function SearchFilters({
  query,
  type,
  minMarketCap,
  maxMarketCap,
  region,
  exchange,
  sector,
  industry,
  onApply,
}) {
  const [draftQuery, setDraftQuery] = useState(query ?? "");
  const [draftType, setDraftType] = useState(type);
  const [draftRange, setDraftRange] = useState(() =>
    indexesFromMarketCapRange(minMarketCap, maxMarketCap)
  );
  const [draftRegion, setDraftRegion] = useState(region ?? "");
  const [draftExchange, setDraftExchange] = useState(exchange ?? "");
  const [draftSector, setDraftSector] = useState(sector ?? "");
  const [draftIndustry, setDraftIndustry] = useState(industry ?? "");

  useEffect(() => {
    setDraftQuery(query ?? "");
  }, [query]);

  useEffect(() => {
    setDraftType(type);
  }, [type]);

  useEffect(() => {
    setDraftRange(indexesFromMarketCapRange(minMarketCap, maxMarketCap));
  }, [minMarketCap, maxMarketCap]);

  useEffect(() => {
    setDraftRegion(region ?? "");
  }, [region]);

  useEffect(() => {
    setDraftExchange(exchange ?? "");
  }, [exchange]);

  useEffect(() => {
    setDraftSector(sector ?? "");
  }, [sector]);

  useEffect(() => {
    setDraftIndustry(industry ?? "");
  }, [industry]);

  const handleSearch = () => {
    onApply({
      q: draftQuery.trim(),
      type: draftType,
      region: draftRegion,
      exchange: draftExchange,
      sector: draftSector,
      industry: draftIndustry,
      ...marketCapRangeFromIndexes(draftRange.lowIndex, draftRange.highIndex),
    });
  };

  const isCleared =
    !draftQuery &&
    !draftType &&
    !draftRegion &&
    !draftExchange &&
    !draftSector &&
    !draftIndustry &&
    draftRange.lowIndex === MARKET_CAP_MIN_INDEX &&
    draftRange.highIndex === MARKET_CAP_MAX_INDEX;

  const handleClear = () => {
    const clearedRange = { lowIndex: MARKET_CAP_MIN_INDEX, highIndex: MARKET_CAP_MAX_INDEX };
    setDraftQuery("");
    setDraftType("");
    setDraftRegion("");
    setDraftExchange("");
    setDraftSector("");
    setDraftIndustry("");
    setDraftRange(clearedRange);
    onApply({
      q: "",
      type: "",
      region: "",
      exchange: "",
      sector: "",
      industry: "",
      ...marketCapRangeFromIndexes(clearedRange.lowIndex, clearedRange.highIndex),
    });
  };

  return (
    <div className="ec-search-filters">
      <div className="ec-search-filters-head">
        <span className="ec-search-filters-title">Filters</span>
        <button
          type="button"
          className="ec-icon-btn"
          onClick={handleClear}
          disabled={isCleared}
          aria-label="Clear filters"
          title="Clear filters"
        >
          <i className="bi bi-arrow-counterclockwise" aria-hidden="true" />
        </button>
      </div>

      <fieldset className="ec-search-filter-group">
        <legend>Keyword</legend>
        <input
          type="text"
          className="ec-input"
          aria-label="Keyword"
          value={draftQuery}
          onChange={(event) => setDraftQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") handleSearch();
          }}
          placeholder="Ticker or company name"
        />
      </fieldset>

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

      <fieldset className="ec-search-filter-group">
        <legend>Region</legend>
        <select
          className="ec-select"
          aria-label="Region"
          value={draftRegion}
          onChange={(event) => setDraftRegion(event.target.value)}
        >
          {REGION_OPTIONS.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </fieldset>

      <fieldset className="ec-search-filter-group">
        <legend>Exchange</legend>
        <select
          className="ec-select"
          aria-label="Exchange"
          value={draftExchange}
          onChange={(event) => setDraftExchange(event.target.value)}
        >
          {EXCHANGE_OPTIONS.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </fieldset>

      <fieldset className="ec-search-filter-group">
        <legend>Sector</legend>
        <select
          className="ec-select"
          aria-label="Sector"
          value={draftSector}
          onChange={(event) => setDraftSector(event.target.value)}
        >
          {SECTOR_OPTIONS.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </fieldset>

      <fieldset className="ec-search-filter-group">
        <legend>Industry</legend>
        <select
          className="ec-select"
          aria-label="Industry"
          value={draftIndustry}
          onChange={(event) => setDraftIndustry(event.target.value)}
        >
          {INDUSTRY_OPTIONS.map((option) => (
            <option key={option.value || "all"} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
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

      <div className="ec-search-filter-actions">
        <Button variant="primary" onClick={handleSearch}>
          Search
        </Button>
      </div>
    </div>
  );
}

export default SearchFilters;
