import { useState } from "react";
import Card from "../../components/core/Card.jsx";
import Button from "../../components/core/Button.jsx";
import Drawer from "../../components/core/Drawer.jsx";
import FieldList from "../../components/core/FieldList.jsx";

const DESCRIPTION_TRUNCATE_LENGTH = 220;

/** Cuts `text` to roughly `limit` characters at the nearest word boundary,
 * appending an ellipsis — the full text is still available via the "See
 * all" Drawer's FieldList, this is just so a long company description
 * doesn't push the rest of the card (CEO/sector/industry) far down. */
function truncate(text, limit) {
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > 0 ? lastSpace : limit)}…`;
}

/**
 * Real company-profile data (description/CEOs/sector/industry) with a
 * "See all" Drawer for the rest of what the profile endpoint returns.
 * Renders nothing when `marketProfile` is null (no data published for this
 * ticker yet) — HoldingTickerPage already surfaces a page-level note for
 * that case, so this section just quietly omits itself rather than
 * duplicating it.
 *
 * @param {{ marketProfile: import("../../api/market.js").MarketProfile|null }} props
 */
function HoldingAboutSection({ marketProfile }) {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  if (!marketProfile) return null;

  const ceos = (Array.isArray(marketProfile.ceos) ? marketProfile.ceos : [])
    .map((c) => `${c.name} (${c.role})`)
    .join(", ");

  return (
    <Card className="ec-detail-section">
      <div className="ec-section-head">
        <h3 className="ec-section-title">About</h3>
        <Button variant="ghost" size="sm" onClick={() => setIsDrawerOpen(true)}>
          See all
        </Button>
      </div>

      {marketProfile.description && (
        <p>{truncate(marketProfile.description, DESCRIPTION_TRUNCATE_LENGTH)}</p>
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

      <Drawer open={isDrawerOpen} onClose={() => setIsDrawerOpen(false)} title="Company profile">
        {marketProfile.description && <p>{marketProfile.description}</p>}
        <FieldList
          items={[
            { label: "Website", value: marketProfile.website },
            { label: "Address", value: marketProfile.address },
            { label: "Country", value: marketProfile.country },
            { label: "Region", value: marketProfile.region },
            { label: "Full-time employees", value: marketProfile.full_time_employees?.toLocaleString() },
            { label: "IPO date", value: marketProfile.ipo_date },
            { label: "Exchange", value: marketProfile.exchange },
            { label: "Quote type", value: marketProfile.quote_type },
            { label: "Last updated", value: marketProfile.last_updated },
            { label: "Source", value: marketProfile.source },
          ]}
        />
      </Drawer>
    </Card>
  );
}

export default HoldingAboutSection;
