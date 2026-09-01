import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AppShell from "../../components/shell/AppShell.jsx";
import Alert from "../../components/core/Alert.jsx";
import Badge from "../../components/core/Badge.jsx";
import Button from "../../components/core/Button.jsx";
import EmptyState from "../../components/core/EmptyState.jsx";
import SearchFilters from "./SearchFilters.jsx";
import { useApi } from "../../api/useApi.js";
import { searchTickers } from "../../api/market.js";
import { MENU_ITEMS } from "../menuItems.js";
import "./SearchPage.css";

const PAGE_SIZE = 25;

/**
 * Results table + left filter pane for ticker search. `q` comes from the
 * URL (TopbarSearch sets it on Enter); `type` mirrors SearchFilters'
 * applied Type selection, the only filter that's real — see
 * SearchFilters.jsx for why Region/Exchange/Market cap are placeholders.
 * Both live in the URL (not just component state) so a search is
 * shareable/bookmarkable and survives a refresh. Clicking a result row
 * does nothing yet — that's a later phase.
 */
function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const type = searchParams.get("type") ?? "";
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
    searchTickers(api, query, { assetClass: type || undefined, page: 1, pageSize: PAGE_SIZE })
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
  }, [api, query, type]);

  const handleLoadMore = () => {
    setIsLoadingMore(true);
    setLoadError(null);
    searchTickers(api, query, {
      assetClass: type || undefined,
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

  const handleApplyFilters = (nextType) => {
    const next = {};
    if (query) next.q = query;
    if (nextType) next.type = nextType;
    setSearchParams(next);
  };

  return (
    <AppShell
      menuItems={MENU_ITEMS}
      eyebrow="Search"
      title="Search"
      subtitle={query ? `Results for “${query}”` : "Search for a ticker or company name."}
      sidebar={<SearchFilters type={type} onApply={handleApplyFilters} />}
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
            <table className="ec-table ec-table--static">
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
                  <tr key={`${result.type}:${result.ticker}`}>
                    <td className="ec-table-name">{result.ticker}</td>
                    <td>{result.name}</td>
                    <td>
                      <Badge tone="neutral">{result.type}</Badge>
                    </td>
                    <td>{result.current_price != null ? result.current_price.toFixed(2) : "—"}</td>
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
