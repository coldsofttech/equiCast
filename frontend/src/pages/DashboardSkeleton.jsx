import Card from "../components/core/Card.jsx";
import Skeleton from "../components/core/Skeleton.jsx";

/**
 * Placeholder for the greeting's title + subtitle (see greeting.js and
 * AppShell's `greeting` prop) shown in its place while useAccounts() is
 * still loading, so the page head doesn't pop in a beat before the account
 * cards below it do.
 */
export function DashboardGreetingSkeleton() {
  return (
    <>
      <Skeleton width="220px" height="1.5rem" />
      <Skeleton width="260px" height="1rem" />
    </>
  );
}

/**
 * Placeholder account cards shown while useAccounts() is still loading —
 * mirrors AccountCard.jsx's layout (icon+name, type badge, description,
 * current value/P&L, pies/holdings counts) inside the same `.ec-account-grid`/
 * `.ec-account-card` classes the real cards use (cardGrid.css), so the grid
 * doesn't jump around once they swap in. Three cards, same reasoning as
 * AccountDetailSkeleton's fixed counts — just enough to fill the grid's
 * first row on a typical viewport without guessing the real account count.
 */
function DashboardSkeleton() {
  return (
    <div className="ec-account-grid">
      {[0, 1, 2].map((i) => (
        <Card className="ec-account-card" key={i}>
          <div className="ec-account-card-head">
            <div className="ec-account-card-title">
              <Skeleton circle width="28px" height="28px" />
              <Skeleton width="100px" height="1rem" />
            </div>
            <Skeleton circle width="56px" height="22px" />
          </div>
          <Skeleton width="80%" height="0.8125rem" />
          <div className="ec-account-card-value">
            <Skeleton width="120px" height="1.5rem" />
            <Skeleton width="90px" height="0.8125rem" />
          </div>
          <div className="ec-account-card-meta">
            <Skeleton width="140px" height="0.75rem" />
          </div>
        </Card>
      ))}
    </div>
  );
}

export default DashboardSkeleton;
