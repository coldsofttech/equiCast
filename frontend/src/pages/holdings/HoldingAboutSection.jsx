import { useState } from "react";
import Card from "../../components/core/Card.jsx";

const DESCRIPTION_TRUNCATE_LENGTH = 220;

/** Cuts `text` to roughly `limit` characters at the nearest word boundary,
 * appending an ellipsis — the full text is still reachable via the
 * "Show more" toggle below, this is just so a long company description
 * doesn't push the rest of the card (CEO/sector/industry) far down by
 * default. */
function truncate(text, limit) {
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > 0 ? lastSpace : limit)}…`;
}

/**
 * Real company-profile data — description (truncated with a "Show
 * more"/"Show less" toggle) plus CEOs/sector/industry/website/address/
 * country/region/full-time employees/IPO date rows, everything the profile
 * endpoint returns. Renders nothing when `marketProfile` is null (no data
 * published for this ticker yet) — HoldingTickerPage already surfaces a
 * page-level note for that case, so this section just quietly omits itself
 * rather than duplicating it.
 *
 * @param {{ marketProfile: import("../../api/market.js").MarketProfile|null }} props
 */
function HoldingAboutSection({ marketProfile }) {
  const [isDescriptionExpanded, setIsDescriptionExpanded] = useState(false);

  if (!marketProfile) return null;

  const ceos = (Array.isArray(marketProfile.ceos) ? marketProfile.ceos : [])
    .map((c) => `${c.name} (${c.role})`)
    .join(", ");

  const description = marketProfile.description;
  const isDescriptionTruncatable = description && description.length > DESCRIPTION_TRUNCATE_LENGTH;

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">About</h3>
      </div>

      {description && (
        <p>
          {isDescriptionExpanded || !isDescriptionTruncatable
            ? description
            : truncate(description, DESCRIPTION_TRUNCATE_LENGTH)}{" "}
          {isDescriptionTruncatable && (
            <button
              type="button"
              className="ec-inline-link-btn"
              onClick={() => setIsDescriptionExpanded((current) => !current)}
            >
              {isDescriptionExpanded ? "Show less" : "Show more"}
            </button>
          )}
        </p>
      )}

      <div className="ec-holding-about-row">
        <span className="ec-field-list-label">CEO</span>
        <span>{ceos || "—"}</span>
      </div>
      <div className="ec-holding-about-row">
        <span className="ec-field-list-label">Sector</span>
        <span>{marketProfile.sector || "—"}</span>
      </div>
      <div className="ec-holding-about-row">
        <span className="ec-field-list-label">Industry</span>
        <span>{marketProfile.industry || "—"}</span>
      </div>
      <div className="ec-holding-about-row">
        <span className="ec-field-list-label">Website</span>
        {marketProfile.website ? (
          <a href={marketProfile.website} target="_blank" rel="noopener noreferrer">
            {marketProfile.website}
          </a>
        ) : (
          <span>—</span>
        )}
      </div>
      <div className="ec-holding-about-row">
        <span className="ec-field-list-label">Address</span>
        <span>{marketProfile.address || "—"}</span>
      </div>
      <div className="ec-holding-about-row">
        <span className="ec-field-list-label">Country</span>
        <span>{marketProfile.country || "—"}</span>
      </div>
      <div className="ec-holding-about-row">
        <span className="ec-field-list-label">Region</span>
        <span>{marketProfile.region || "—"}</span>
      </div>
      <div className="ec-holding-about-row">
        <span className="ec-field-list-label">Full-time employees</span>
        <span>{marketProfile.full_time_employees?.toLocaleString() || "—"}</span>
      </div>
      <div className="ec-holding-about-row">
        <span className="ec-field-list-label">IPO date</span>
        <span>{marketProfile.ipo_date || "—"}</span>
      </div>
    </Card>
  );
}

export default HoldingAboutSection;
