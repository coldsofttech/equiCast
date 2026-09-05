import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import Alert from "../../components/core/Alert.jsx";
import AssetTypeBadge from "../../components/core/AssetTypeBadge.jsx";
import AssetIcon from "../../components/core/AssetIcon.jsx";
import Button from "../../components/core/Button.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import SearchFilters from "./SearchFilters.jsx";
import { useApi } from "../../api/useApi.js";
import { searchTickers } from "../../api/market.js";
import { formatCurrency } from "../sampleFinancials.js";
import { MENU_ITEMS } from "../menuItems.js";
import "./SearchPage.css";

const PAGE_SIZE = 25;

/**
 * Results table + left filter pane for ticker search. `q` comes from the
 * URL (TopbarSearch sets it on Enter); `type`/`minCap`/`maxCap` mirror
 * SearchFilters' applied Type/Market cap selections, the two filters
 * that are real — see SearchFilters.jsx for why Region/Exchange are still
 * placeholders. All four live in the URL (not just component state) so a
 * search is shareable/bookmarkable and survives a refresh. Clicking a
 * result row goes to its holding detail page (HoldingTickerPage handles a
 * ticker the user doesn't actually hold with its own empty state).
 */
function SearchPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const type = searchParams.get("type") ?? "";
  const minCapParam = searchParams.get("minCap");
  const maxCapParam = searchParams.get("maxCap");
  const minMarketCap = minCapParam != null ? Number(minCapParam) : undefined;
  const maxMarketCap = maxCapParam != null ? Number(maxCapParam) : undefined;
  const api = useApi();

  const [results, setResults] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [count, setCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setCount(0);
      setTotalPages(0);
      return undefined;
    }

    let cancelled = false;
    setIsLoading(true);
    setLoadError(null);
    searchTickers(api, query, {
      assetClass: type || undefined,
      minMarketCap,
      maxMarketCap,
      page: 1,
      pageSize: PAGE_SIZE,
    })
      .then((response) => {
        if (cancelled) return;
        setResults(response.results);
        setPage(1);
        setTotalPages(response.total_pages);
        setCount(response.count);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message ?? "Search failed.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api, query, type, minMarketCap, maxMarketCap]);

  const handleLoadMore = () => {
    setIsLoadingMore(true);
    setLoadError(null);
    searchTickers(api, query, {
      assetClass: type || undefined,
      minMarketCap,
      maxMarketCap,
      page: page + 1,
      pageSize: PAGE_SIZE,
    })
      .then((response) => {
        setResults((current) => [...current, ...response.results]);
        setPage((current) => current + 1);
      })
      .catch((err) => setLoadError(err.message ?? "Couldn't load more results."))
      .finally(() => setIsLoadingMore(false));
  };

  const handleApplyFilters = ({ type: nextType, minMarketCap: nextMin, maxMarketCap: nextMax }) => {
    const next = {};
    if (query) next.q = query;
    if (nextType) next.type = nextType;
    if (nextMin != null) next.minCap = String(nextMin);
    if (nextMax != null) next.maxCap = String(nextMax);
    setSearchParams(next);
  };

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Search"
      title="Search"
      subtitle={query ? `Results for “${query}”` : "Search for a ticker or company name."}
      sidebar={
        <SearchFilters
          type={type}
          minMarketCap={minMarketCap}
          maxMarketCap={maxMarketCap}
          onApply={handleApplyFilters}
        />
      }
    >
      {loadError && <Alert tone="danger">{loadError}</Alert>}

      {!query.trim() ? (
        <EmptyState
          title="Search for a ticker"
          description="Use the search box in the top bar to look up a stock, ETF or FX pair."
        />
      ) : isLoading ? (
        <p className="ec-loading">Searching…</p>
      ) : results.length === 0 ? (
        <EmptyState
          title="No matches"
          description={`No tickers matched “${query}”. Try a different name or ticker, or adjust the filters.`}
        />
      ) : (
        <>
          <p className="ec-search-count">
            {count} match{count === 1 ? "" : "es"}
          </p>
          <div className="ec-table-wrap">
            <table className="ec-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Price</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result) => (
                  <tr
                    key={`${result.type}:${result.ticker}`}
                    onClick={() =>
                      navigate(`/holdings/${result.ticker}`, { state: { assetClass: result.type } })
                    }
                  >
                    <td className="ec-table-name">
                      <span className="ec-search-result-ticker">
                        <AssetIcon website={result.website} size={20} />
                        {result.ticker}
                      </span>
                    </td>
                    <td>{result.name}</td>
                    <td>
                      <AssetTypeBadge type={result.type} />
                    </td>
                    <td>
                      {result.current_price != null
                        ? result.currency
                          ? formatCurrency(result.current_price, result.currency)
                          : result.current_price.toFixed(2)
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {page < totalPages && (
            <div className="ec-search-load-more">
              <Button variant="secondary" onClick={handleLoadMore} isLoading={isLoadingMore}>
                Load more
              </Button>
            </div>
          )}
        </>
      )}
    </AppShell>
  );
}

export default SearchPage;
