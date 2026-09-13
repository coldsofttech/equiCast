/**
 * Client-side range picking/slicing for the price chart (HoldingPriceChart.jsx/
 * PiePriceChart.jsx) — GET .../prices/ now returns one bundled
 * `{daily, weekly, monthly}` payload per ticker (see api/market.js's
 * getPrices) instead of one already-trimmed `prices` array per range, so
 * switching the range picker no longer fetches anything (GitHub issue
 * #150); `sliceForRange` below does client-side what the backend's
 * `equicast_core.client.get_prices`/`_start_date_for_range` used to do
 * server-side per request.
 *
 * `RANGES`/`LONG_RANGES`/`VERY_LONG_RANGES`/`formatAxisDate` were
 * previously duplicated verbatim in both chart components — shared here
 * instead.
 */

/** Every range this picker offers, in display order. "1d" is deliberately
 * excluded — only daily bars are ever stored, so a "1 day" range would
 * just be the single latest one. */
export const RANGES = [
  { id: "5d", label: "1W" },
  { id: "1m", label: "1M" },
  { id: "6m", label: "6M" },
  { id: "ytd", label: "YTD" },
  { id: "1y", label: "1Y" },
  { id: "2y", label: "2Y" },
  { id: "3y", label: "3Y" },
  { id: "5y", label: "5Y" },
  { id: "10y", label: "10Y" },
  { id: "max", label: "MAX" },
];

/** Used only to pick a coarser x-axis date format, not to re-slice
 * anything — see `formatAxisDate`. */
export const LONG_RANGES = new Set(["2y", "3y", "5y", "10y", "max"]);
export const VERY_LONG_RANGES = new Set(["10y", "max"]);

export function formatAxisDate(dateStr, rangeId) {
  const d = new Date(dateStr);
  if (VERY_LONG_RANGES.has(rangeId)) return d.toLocaleDateString(undefined, { year: "numeric" });
  if (LONG_RANGES.has(rangeId)) return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

/** JS port of equicast_core.client._start_date_for_range — the calendar
 * date `months` months before `today`, clamping the day-of-month to the
 * target month's own last day (e.g. Mar 31 minus 1 month -> Feb 28/29, not
 * an invalid Feb 31). Returns a "YYYY-MM-DD" string so it compares
 * directly against a PriceBar's own `date` string. */
function startDateForRange(months, today) {
  const monthIndex = today.getMonth() - months;
  const year = today.getFullYear() + Math.floor(monthIndex / 12);
  const month0 = ((monthIndex % 12) + 12) % 12;
  const daysInMonth = new Date(year, month0 + 1, 0).getDate();
  const day = Math.min(today.getDate(), daysInMonth);
  return `${year}-${pad2(month0 + 1)}-${pad2(day)}`;
}

/** Month-based cutoff width per range that needs one — mirrors
 * equicast_core.client._PRICE_RANGE_MONTHS. "5d" trims by trailing row
 * count instead (see below), "2y"/"max" need no cutoff at all since
 * they're exactly what `history.weekly`/`history.monthly` already cover. */
const RANGE_MONTHS = { "1m": 1, "6m": 6, "1y": 12, "3y": 36, "5y": 60, "10y": 120 };

/**
 * Which of `RANGES` are worth offering at all, given `earliestDate` (the
 * real earliest date this chart could ever show — e.g. a since-inception
 * portfolio chart's own first-investment date). `null` skips filtering
 * entirely, showing every preset. "5d"/"ytd"/"max" are always offered —
 * "5d" and "ytd" are distinct, commonly useful windows regardless of total
 * history length, and "max" is the permanent catch-all the range picker
 * always defaults to. For the remaining month-based presets, only the
 * *first* (smallest) one whose own cutoff already reaches back on/before
 * `earliestDate` is kept — any larger preset past it would show the exact
 * same data, so it's dropped as redundant (mirrors holdingFinancials.js's
 * `availablePastRanges`, same "if the data doesn't go back that far, the
 * bigger button doesn't make sense" reasoning).
 *
 * @param {string|null} earliestDate - "YYYY-MM-DD"
 * @param {Date} [today] - overridable for tests.
 * @returns {typeof RANGES}
 */
export function visibleRanges(earliestDate, today = new Date()) {
  if (!earliestDate) return RANGES;

  const always = new Set(["5d", "ytd", "max"]);
  const kept = new Set(always);
  for (const range of RANGES) {
    if (always.has(range.id)) continue;
    kept.add(range.id);
    const months = range.id === "2y" ? 24 : RANGE_MONTHS[range.id];
    if (startDateForRange(months, today) <= earliestDate) break;
  }
  return RANGES.filter((r) => kept.has(r.id));
}

/**
 * Picks and trims the right segment of `history` (see api/market.js's
 * `PriceSeries` typedef — `{ daily, weekly, monthly }`) for `rangeId`,
 * entirely client-side. `today` is overridable for tests.
 *
 * @param {{ daily?: import("../api/market.js").PriceBar[], weekly?: import("../api/market.js").PriceBar[], monthly?: import("../api/market.js").PriceBar[] }|null|undefined} history
 * @param {string} rangeId - one of RANGES' ids
 * @param {Date} [today]
 * @returns {import("../api/market.js").PriceBar[]}
 */
export function sliceForRange(history, rangeId, today = new Date()) {
  const { daily = [], weekly = [], monthly = [] } = history ?? {};

  switch (rangeId) {
    case "5d":
      return daily.slice(-5);
    case "1m":
    case "6m":
      return daily.filter((bar) => bar.date >= startDateForRange(RANGE_MONTHS[rangeId], today));
    case "ytd":
      return daily.filter((bar) => bar.date >= `${today.getFullYear()}-01-01`);
    case "1y":
      return weekly.filter((bar) => bar.date >= startDateForRange(12, today));
    case "2y":
      return weekly;
    case "3y":
    case "5y":
    case "10y":
      return monthly.filter((bar) => bar.date >= startDateForRange(RANGE_MONTHS[rangeId], today));
    case "max":
    default:
      return monthly;
  }
}
