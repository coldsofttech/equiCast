import Badge from "./Badge.jsx";

/** Full label per asset type — TopbarSearch/TickerSearchField/SearchPage/
 * HoldingComparePicker all render the same set, so one mapping instead of
 * each spelling it out. */
const ASSET_TYPE_LABELS = { stock: "Stock", etf: "ETF", fx: "FX", benchmark: "Benchmark" };

/** `tone` per asset type, kept distinct from the tones a market profile's
 * own badges use (see MARKET_PROFILE_BADGE_TONES in api/market.js —
 * exchange/quoteType/synced) so a page showing both never repeats a color
 * for two different meanings. */
const ASSET_TYPE_BADGE_TONES = {
  stock: "success",
  etf: "purple",
  fx: "warning",
  benchmark: "danger",
};

/**
 * A `Badge` for a search result's/holding's asset type — shared by
 * TopbarSearch's dropdown, TickerSearchField, SearchPage and
 * HoldingComparePicker instead of each spelling out the label/tone for
 * "stock"/"etf"/"fx"/"benchmark" itself.
 *
 * @param {{ type: "stock"|"etf"|"fx"|"benchmark" } & Omit<React.ComponentProps<typeof Badge>, "tone">} props
 */
function AssetTypeBadge({ type, ...rest }) {
  return (
    <Badge tone={ASSET_TYPE_BADGE_TONES[type] ?? "neutral"} {...rest}>
      {ASSET_TYPE_LABELS[type] ?? type}
    </Badge>
  );
}

export default AssetTypeBadge;
