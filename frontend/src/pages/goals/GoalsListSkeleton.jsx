import Skeleton from "../../components/core/Skeleton.jsx";
import "./Goals.css";

const ROW_COUNT = 4;

/**
 * Placeholder rows shown in place of the real goals table while useGoals()
 * is still loading — mirrors GoalsListPage's real layout (the "Show
 * Achieved" switch above an `ec-table` with Name/Purpose/Account-Pie/
 * Progress/Target date columns) so the page doesn't jump around once the
 * real rows swap in. Same `ROW_COUNT`-fixed-rows reasoning as SearchSkeleton.
 */
function GoalsListSkeleton() {
  return (
    <>
      <div className="ec-section-head">
        <span />
        <Skeleton width="120px" height="1.25rem" />
      </div>

      <div className="ec-table-wrap">
        <table className="ec-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Purpose</th>
              <th>Account/Pie</th>
              <th>Progress</th>
              <th>Target date</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: ROW_COUNT }, (_, i) => (
              <tr key={i}>
                <td>
                  <div className="ec-table-name-cell">
                    <Skeleton circle width="28px" height="28px" />
                    <div>
                      <Skeleton width="120px" height="0.9rem" />
                      <Skeleton width="90px" height="0.75rem" />
                    </div>
                  </div>
                </td>
                <td>
                  <Skeleton width="70px" height="1.25rem" />
                </td>
                <td>
                  <Skeleton width="100px" height="0.85rem" />
                </td>
                <td>
                  <Skeleton circle width="32px" height="32px" />
                </td>
                <td>
                  <Skeleton width="80px" height="0.85rem" />
                </td>
                <td />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default GoalsListSkeleton;
