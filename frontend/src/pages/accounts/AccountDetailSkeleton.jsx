import Card from "../../components/core/Card.jsx";
import Skeleton from "../../components/core/Skeleton.jsx";
import "../holdings/HoldingTickerSkeleton.css";
import "../holdings/HoldingTickerPage.css";

/**
 * Placeholder "cards" shown in place of the real account detail content
 * while GET /accounts/<id> is still loading — mirrors AccountDetailPage's
 * real layout (StatTiles row, price chart card, the
 * two-column Portfolios/Holdings row lists, Sector/Industry/Asset/
 * Market-cap allocation cards, CAGR card, Holdings heatmap card) so the page
 * doesn't jump around once the real content swaps in. Every section here renders
 * unconditionally, same reasoning as PieDetailSkeleton — an account is only
 * ever reached once it's known to exist. Reuses the `ec-skeleton-*`/
 * `ec-cagr-*` utility classes HoldingTickerSkeleton.jsx and
 * PieCagrSection.jsx already define rather than duplicating them.
 */
function AccountDetailSkeleton() {
  return (
    <>
      <div className="ec-stat-grid">
        {[0, 1, 2].map((i) => (
          <div className="ec-stat-tile" key={i}>
            <Skeleton width="70%" height="0.75rem" />
            <Skeleton width="85%" height="1.5rem" />
          </div>
        ))}
      </div>

      <Card className="ec-pchart">
        <div className="ec-skeleton-toolbar">
          <Skeleton width="180px" height="2rem" />
          <Skeleton width="160px" height="2rem" />
        </div>
        <Skeleton width="100%" height="1.75rem" className="ec-skeleton-block" />
        <Skeleton width="100%" height="260px" className="ec-skeleton-block" />
      </Card>

      <div className="ec-account-columns">
        <div>
          <div className="ec-section-head">
            <Skeleton width="110px" height="1.25rem" />
          </div>
          <div className="ec-detail-row-list">
            {[0, 1].map((i) => (
              <Card className="ec-detail-row" key={i}>
                <div className="ec-detail-row-main">
                  <Skeleton width="140px" height="0.9rem" />
                  <Skeleton width="90px" height="0.75rem" />
                </div>
                <div className="ec-detail-row-value">
                  <Skeleton width="70px" height="0.9rem" />
                  <Skeleton width="60px" height="0.75rem" />
                </div>
              </Card>
            ))}
          </div>
        </div>

        <div>
          <div className="ec-section-head">
            <Skeleton width="90px" height="1.25rem" />
          </div>
          <div className="ec-detail-row-list">
            {[0, 1].map((i) => (
              <Card className="ec-detail-row" key={i}>
                <div className="ec-detail-row-main">
                  <Skeleton width="140px" height="0.9rem" />
                  <Skeleton width="90px" height="0.75rem" />
                </div>
                <div className="ec-detail-row-value">
                  <Skeleton width="70px" height="0.9rem" />
                  <Skeleton width="60px" height="0.75rem" />
                </div>
              </Card>
            ))}
          </div>
        </div>
      </div>

      <div className="ec-divchart-grid">
        {[0, 1, 2, 3].map((i) => (
          <Card className="ec-divchart ec-detail-section" key={i}>
            <div className="ec-divchart-head">
              <Skeleton width="160px" height="1.1rem" />
            </div>
            {[0, 1, 2].map((j) => (
              <div className="ec-divchart-row" key={j}>
                <Skeleton width="90px" height="0.75rem" />
                <Skeleton width="100%" height="10px" />
                <Skeleton width="30px" height="0.75rem" />
              </div>
            ))}
          </Card>
        ))}
      </div>

      <Card className="ec-detail-section">
        <Skeleton width="60px" height="1.25rem" />
        <div className="ec-cagr-list">
          {[0, 1, 2].map((i) => (
            <div className="ec-cagr-row" key={i}>
              <Skeleton width="30px" height="0.75rem" />
              <Skeleton width="100%" height="0.75rem" />
              <Skeleton width="50px" height="0.75rem" />
            </div>
          ))}
        </div>
      </Card>

      <Card className="ec-detail-section">
        <Skeleton width="140px" height="1.1rem" />
        <Skeleton width="100%" height="240px" className="ec-skeleton-block" />
      </Card>
    </>
  );
}

export default AccountDetailSkeleton;
