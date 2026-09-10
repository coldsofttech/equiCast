import Card from "../../components/core/Card.jsx";
import Skeleton from "../../components/core/Skeleton.jsx";
import "./HoldingTickerSkeleton.css";

/**
 * Placeholder "cards" shown in place of the real page content while the
 * market profile/transactions/price chart/dividends are still loading —
 * mirrors the real layout below (StatTiles row, price chart card, Owned
 * shares table, CAGR card, Buy/Sell Rating card, Stats/About columns,
 * Dividends cards, Recent activity card) so the page doesn't jump around
 * once the real content swaps in. `isOwned` hides the StatTiles/Owned
 * shares/Recent activity rows for a ticker the user doesn't hold, same as
 * the real content does — the CAGR and Buy/Sell Rating cards aren't gated
 * on it, since HoldingCagrSection.jsx/HoldingBuySellGauge.jsx render off
 * market metrics regardless of ownership. The Dividends card grid and the
 * Transactions row list each always render three placeholders regardless
 * of how many (if any) the real sections end up showing — neither's real
 * count is known until the real fetch resolves, so this can't match either
 * exactly. Transactions mirrors HoldingTransactionsSection's AVERAGE-mode
 * row list (the default transaction_type — see HoldingTickerPage.jsx's
 * `userProfile?.transaction_type ?? "AVERAGE"`), not its TRANSACTION-mode
 * card grid, since the two modes' layouts differ and the profile that picks
 * between them may not have loaded yet.
 *
 * @param {{ isOwned: boolean }} props
 */
function HoldingTickerSkeleton({ isOwned }) {
  return (
    <>
      {isOwned && (
        <div className="ec-stat-grid">
          {[0, 1, 2, 3].map((i) => (
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
        <Skeleton width="130px" height="1.25rem" />
        <div className="ec-buysell-head">
          <Skeleton width="40px" height="1.25rem" />
          <Skeleton width="120px" height="0.75rem" />
          <Skeleton width="40px" height="1.25rem" />
        </div>
        <Skeleton width="100%" height="10px" />
      </Card>

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

      {isOwned && (
        <Card className="ec-detail-section">
          <div className="ec-section-head">
            <Skeleton width="120px" height="1.25rem" />
            <div className="ec-section-head-actions">
              <Skeleton width="60px" height="1rem" />
              <Skeleton width="90px" height="1rem" />
              <Skeleton width="50px" height="1rem" />
            </div>
          </div>
          <div className="ec-transaction-row-list">
            {[0, 1, 2].map((i) => (
              <div className="ec-transaction-row-card" key={i}>
                <Skeleton width="28px" height="28px" circle />
                <Skeleton width="100%" height="0.875rem" className="ec-transaction-row-date" />
                <Skeleton width="70px" height="0.875rem" />
              </div>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

export default HoldingTickerSkeleton;
