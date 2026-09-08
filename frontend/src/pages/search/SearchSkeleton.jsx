import Skeleton from "../../components/core/Skeleton.jsx";
import "./SearchPage.css";

const ROW_COUNT = 8;

/**
 * Placeholder rows shown in place of the real search results table while
 * searchTickers is still resolving — mirrors SearchPage's real result count
 * line + `ec-table` (Ticker/Name/Type/Price columns) so the page doesn't
 * jump around once the real rows swap in. SearchFilters (the sidebar) isn't
 * gated on this loading state, so it isn't part of this skeleton.
 */
function SearchSkeleton() {
  return (
    <>
      <Skeleton width="90px" height="0.8rem" className="ec-search-count" />
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
            {Array.from({ length: ROW_COUNT }, (_, i) => (
              <tr key={i}>
                <td className="ec-table-name">
                  <span className="ec-search-result-ticker">
                    <Skeleton circle width="20px" height="20px" />
                    <Skeleton width="60px" height="0.85rem" />
                  </span>
                </td>
                <td>
                  <Skeleton width="140px" height="0.85rem" />
                </td>
                <td>
                  <Skeleton width="70px" height="1.25rem" />
                </td>
                <td>
                  <Skeleton width="60px" height="0.85rem" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default SearchSkeleton;
