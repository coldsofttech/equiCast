import Card from "../../components/core/Card.jsx";
import Skeleton from "../../components/core/Skeleton.jsx";
import "./HoldingTickerSkeleton.css";

/**
 * Placeholder "cards" shown in place of the real page content while the
 * market profile/transactions/price chart/dividends are still loading —
 * mirrors the real layout below (StatTiles row, price chart card, Owned
 * shares table, Stats/About columns, Dividends cards) so the page doesn't
 * jump around once the real content swaps in. `isOwned` hides the
 * StatTiles/Owned shares rows for a ticker the user doesn't hold, same as
 * the real content does. The Dividends placeholder always renders three
 * cards regardless of how many (if any) the real section ends up showing —
 * HoldingDividendsSection.jsx's own upcoming-dividends count isn't known
 * until the real fetch resolves, so this can't match it exactly.
 *
 * @param {{ isOwned: boolean }} props
 */
function HoldingTickerSkeleton({ isOwned }) {
  return (
    <>
      {isOwned && (
        <div className="ec-stat-grid">
          {[0, 1, 2].map((i) => (
            <div className="ec-stat-tile" key={i}>
              <Skeleton width="70%" height="0.75rem" />
              <Skeleton width="85%" height="1.5rem" />
            </div>
          ))}
        </div>
      )}

      <Card className="ec-pchart">
        <div className="ec-skeleton-toolbar">
          <Skeleton width="180px" height="2rem" />
          <Skeleton width="160px" height="2rem" />
        </div>
        <Skeleton width="100%" height="1.75rem" className="ec-skeleton-block" />
        <Skeleton width="100%" height="260px" className="ec-skeleton-block" />
      </Card>

      {isOwned && (
        <>
          <div className="ec-section-head">
            <Skeleton width="140px" height="1.25rem" />
          </div>
          <Card>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} width="100%" height="40px" className="ec-skeleton-row" />
            ))}
          </Card>
        </>
      )}

      <div className="ec-account-columns">
        <Card className="ec-detail-section">
          <Skeleton width="80px" height="1.25rem" />
          <div className="ec-holding-highlow-grid">
            {[0, 1].map((i) => (
              <div className="ec-skeleton-range-col" key={i}>
                <Skeleton width="70px" height="0.75rem" />
                <Skeleton width="10px" height="64px" />
                <Skeleton width="70px" height="0.75rem" />
              </div>
            ))}
          </div>
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} width="100%" height="1rem" className="ec-skeleton-row" />
          ))}
        </Card>

        <Card className="ec-detail-section">
          <Skeleton width="80px" height="1.25rem" />
          <Skeleton width="100%" height="1rem" className="ec-skeleton-row" />
          <Skeleton width="100%" height="1rem" className="ec-skeleton-row" />
          <Skeleton width="60%" height="1rem" className="ec-skeleton-row" />
        </Card>
      </div>

      <Card className="ec-detail-section">
        <Skeleton width="90px" height="1.25rem" />
        <div className="ec-dividend-grid">
          {[0, 1, 2].map((i) => (
            <div className="ec-dividend-card" key={i}>
              <Skeleton width="70px" height="1.25rem" />
              <Skeleton width="60px" height="1.5rem" />
              <div className="ec-dividend-fields-row">
                <Skeleton width="80px" height="2rem" />
                <Skeleton width="80px" height="2rem" />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

export default HoldingTickerSkeleton;
