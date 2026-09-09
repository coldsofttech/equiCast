import { useState } from "react";
import Card from "../../components/core/Card.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import "./HoldingTickerPage.css";

/** Up to this many articles show in the main (non-drawer) grid — the rest
 * are only reachable via "See all", same cap-then-drawer pattern
 * HoldingDividendsSection uses for upcoming-dividend cards. `news` is
 * already newest-first from the API (see api/market.js's getNews), so this
 * is simply the first N. */
const MAIN_GRID_LIMIT = 8;

/** An ISO datetime (`published_at`) as "10 Sep 2026" — same short format
 * HoldingDividendsSection's formatDividendDate uses, just parsing a full
 * datetime instead of a bare date. */
function formatPublishedDate(isoDatetime) {
  const date = new Date(isoDatetime);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** One news card — thumbnail (when yfinance reported one), title, and
 * publisher/date, opening the article in a new tab on click. The whole
 * card is the link (not just the title) so a click anywhere on it acts the
 * same way as clicking a search result. */
function NewsCard({ article }) {
  return (
    <a
      className="ec-news-card"
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
    >
      {article.thumbnail_url && (
        <img className="ec-news-card-thumb" src={article.thumbnail_url} alt="" loading="lazy" />
      )}
      <div className="ec-news-card-body">
        <span className="ec-news-card-title">{article.title}</span>
        <div className="ec-news-card-meta">
          {article.publisher && <span className="ec-news-card-publisher">{article.publisher}</span>}
          <span className="ec-news-card-date">{formatPublishedDate(article.published_at)}</span>
        </div>
      </div>
    </a>
  );
}

/**
 * Up to MAIN_GRID_LIMIT news cards (3-4 per row, responsive), newest first,
 * plus a "See all" button opening a Drawer with the full, scrollable list
 * when there are more than that. Each card opens the article in a new tab
 * on click.
 *
 * Renders nothing when `news` is null (no data published yet, including
 * every fx ticker - the fx ingestion pipeline never writes news.parquet)
 * or carries no articles at all.
 *
 * @param {{ news: import("../../api/market.js").NewsResponse|null }} props
 */
function HoldingNewsSection({ news }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const articles = news?.news ?? [];
  if (articles.length === 0) return null;

  const mainArticles = articles.slice(0, MAIN_GRID_LIMIT);
  const hasMore = articles.length > MAIN_GRID_LIMIT;

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">News</h3>
        {hasMore && (
          <button type="button" className="ec-inline-link-btn" onClick={() => setIsDrawerOpen(true)}>
            See all
          </button>
        )}
      </div>

      <div className="ec-news-grid">
        {mainArticles.map((article) => (
          <NewsCard article={article} key={article.id} />
        ))}
      </div>

      <Drawer open={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} title="News">
        <div className="ec-news-list">
          {articles.map((article) => (
            <NewsCard article={article} key={article.id} />
          ))}
        </div>
      </Drawer>
    </Card>
  );
}

export default HoldingNewsSection;
