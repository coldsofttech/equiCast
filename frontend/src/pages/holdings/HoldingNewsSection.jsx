import { useLayoutEffect, useRef, useState } from "react";
import Card from "../../components/core/Card.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import "./HoldingTickerPage.css";

/** Mirrors `.ec-news-grid`'s `grid-template-columns: repeat(auto-fit,
 * minmax(MIN_CARD_WIDTH, 1fr))` and its gap (--ec-s-16) — used to work out
 * how many cards the grid can actually fit in one row at its current
 * width, so the main grid always shows a full row rather than a fixed
 * count that can leave a lone card stretched full-width in a partial last
 * row (equicast-support#177). */
const MIN_CARD_WIDTH = 220;
const GRID_GAP = 16;

/** Grid width assumed before the first real ResizeObserver measurement,
 * and in environments without ResizeObserver (e.g. jsdom in tests) —
 * resolves to 4 columns via columnsForWidth, matching this panel's
 * previous fixed default. */
const DEFAULT_GRID_WIDTH = 960;

/** How many cards fit in one row of `.ec-news-grid` at a given container
 * width, following the same auto-fit/minmax math the CSS grid itself
 * uses: columns keep growing while another MIN_CARD_WIDTH-wide track
 * (plus its gap) still fits. */
function columnsForWidth(width) {
  return Math.max(1, Math.floor((width + GRID_GAP) / (MIN_CARD_WIDTH + GRID_GAP)));
}

/** Max characters for a title in the "See all" drawer's table before it's
 * truncated (word-boundary, like HoldingAboutSection's own `truncate`) —
 * keeps one row from dwarfing the rest when yfinance hands back an
 * unusually long headline. */
const TITLE_TRUNCATE_LIMIT = 70;

/** An ISO datetime (`published_at`) as "10 Sep 2026" — same short format
 * HoldingDividendsSection's formatDividendDate uses, just parsing a full
 * datetime instead of a bare date. */
function formatPublishedDate(isoDatetime) {
  const date = new Date(isoDatetime);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

/** Same word-boundary truncation as HoldingAboutSection's `truncate` — cuts
 * at `limit`, then backs up to the last space so a word isn't split mid-way,
 * appending an ellipsis. */
function truncate(text, limit) {
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > 0 ? lastSpace : limit)}…`;
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

/** One news row in the "See all" drawer's table — thumbnail, date,
 * publisher, title (truncated to TITLE_TRUNCATE_LIMIT, full text in a
 * `title` attribute for hover), same clickable-row-opens-the-thing pattern
 * HoldingInstancesTable/AccountsListPage's tables use, except this
 * navigates off-site (the article) rather than to another in-app route, so
 * it opens in a new tab instead of via useNavigate. */
function NewsTableRow({ article }) {
  return (
    <tr onClick={() => window.open(article.url, "_blank", "noopener,noreferrer")}>
      <td>
        {article.thumbnail_url && (
          <img className="ec-news-table-thumb" src={article.thumbnail_url} alt="" loading="lazy" />
        )}
      </td>
      <td>{formatPublishedDate(article.published_at)}</td>
      <td>{article.publisher}</td>
      <td className="ec-news-table-title" title={article.title}>
        {article.title ? truncate(article.title, TITLE_TRUNCATE_LIMIT) : article.title}
      </td>
    </tr>
  );
}

/**
 * A full row of news cards (column count follows the panel's real width,
 * see columnsForWidth), newest first, plus a "See all" button opening a
 * Drawer with the full list as a table (thumbnail, date, publisher, title)
 * when there are more articles than fit in that row. Each card/row opens
 * the article in a new tab on click.
 *
 * Renders nothing when `news` is null (no data published yet, including
 * every fx ticker - the fx ingestion pipeline never writes news.parquet)
 * or carries no articles at all.
 *
 * @param {{ news: import("../../api/market.js").NewsResponse|null }} props
 */
function HoldingNewsSection({ news }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const gridRef = useRef(null);
  const [gridWidth, setGridWidth] = useState(DEFAULT_GRID_WIDTH);

  useLayoutEffect(() => {
    const el = gridRef.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const boxWidth = entries[0]?.contentRect.width;
      if (boxWidth) setGridWidth(boxWidth);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const articles = news?.news ?? [];
  if (articles.length === 0) return null;

  const mainGridLimit = columnsForWidth(gridWidth);
  const mainArticles = articles.slice(0, mainGridLimit);
  const hasMore = articles.length > mainGridLimit;

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

      <div className="ec-news-grid" ref={gridRef}>
        {mainArticles.map((article) => (
          <NewsCard article={article} key={article.id} />
        ))}
      </div>

      <Drawer open={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} title="News">
        <div className="ec-table-wrap">
          <table className="ec-table">
            <thead>
              <tr>
                <th aria-label="Thumbnail" />
                <th>Date</th>
                <th>Publisher</th>
                <th>Title</th>
              </tr>
            </thead>
            <tbody>
              {articles.map((article) => (
                <NewsTableRow article={article} key={article.id} />
              ))}
            </tbody>
          </table>
        </div>
      </Drawer>
    </Card>
  );
}

export default HoldingNewsSection;
