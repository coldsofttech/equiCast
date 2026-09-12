import ComingSoonPage from "../ComingSoonPage.jsx";

/**
 * Placeholder for GitHub issue #170's "Watchlists" menu entry — the
 * backend (backend/watchlists/) already exists and is used elsewhere
 * (e.g. watchlist-scoped holdings), but has no frontend page yet. Replace
 * this with the real list/detail UI once that's built.
 */
function WatchlistsPage() {
  return (
    <ComingSoonPage
      eyebrow="Watchlists"
      title="Watchlists"
      icon="bi-binoculars"
      message="Track tickers you don't hold yet, right alongside your accounts. This page is on its way."
    />
  );
}

export default WatchlistsPage;
