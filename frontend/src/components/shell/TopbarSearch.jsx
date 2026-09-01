import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./TopbarSearch.css";

/**
 * The topbar's ticker/company search box — Enter routes to /search?q=...;
 * SearchPage owns actually running the query (and any filters) once
 * there, this is purely a fast way to get there with an initial query.
 */
function TopbarSearch() {
  const navigate = useNavigate();
  const [value, setValue] = useState("");

  const handleKeyDown = (event) => {
    if (event.key !== "Enter") return;
    const trimmed = value.trim();
    if (!trimmed) return;
    navigate(`/search?q=${encodeURIComponent(trimmed)}`);
  };

  return (
    <div className="ec-topbar-search">
      <i className="bi bi-search" aria-hidden="true" />
      <input
        type="search"
        className="ec-topbar-search-input"
        placeholder="Search tickers…"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        aria-label="Search tickers"
      />
    </div>
  );
}

export default TopbarSearch;
