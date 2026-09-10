import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import Balance from "../../components/core/Balance.jsx";
import Card from "../../components/core/Card.jsx";
import Modal from "../../components/core/Modal.jsx";
import { useApi } from "../../api/useApi.js";
import { getEvents, getPrices } from "../../api/market.js";
import { formatPrice } from "./holdingFinancials.js";
import HoldingBenchmarkRating from "./HoldingBenchmarkRating.jsx";
import HoldingComparePicker from "./HoldingComparePicker.jsx";
import "../accounts/PriceChart.css";
import "./HoldingPriceChart.css";

/** Label/CSS-modifier per `EventRecord.event_type` (see market.js) — one
 * mapping so the toggle's dots/legend and the hover tooltip's own heading
 * agree on what each type is called. */
const EVENT_TYPE_META = {
  earnings: { label: "Earnings" },
  rating: { label: "Analyst Rating" },
  split: { label: "Stock Split" },
};

/** The bar index whose own trading day an event's `date` falls on or most
 * recently follows (binary search over `bars`, sorted ascending by
 * `date`) — `-1` if `date` is before every bar (e.g. a very old event on a
 * ticker whose price history doesn't reach back that far in the current
 * range). An event dated on a weekend/holiday lands on the prior trading
 * day's bar, the same "nearest day on or before" rule
 * `equicast_core.client.get_price_on_date` uses server-side. */
function barIndexForDate(bars, targetDate) {
  let lo = 0;
  let hi = bars.length - 1;
  let result = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (bars[mid].date <= targetDate) {
      result = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return result;
}

/** Every range this picker offers (see market.js's PRICE_RANGES for the
 * full set the backend accepts) — "1d" is deliberately omitted: only
 * daily bars are ever stored, so a "1 day" range would just be the single
 * latest row, not a meaningful chart. */
const RANGES = [
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

/** Ranges the backend returns weekly/monthly-aggregated bars for (see
 * equicast_core.client's _PRICE_RANGE_GRANULARITY) — used here only to
 * pick a coarser x-axis date format, not to re-aggregate anything. */
const LONG_RANGES = new Set(["2y", "3y", "5y", "10y", "max"]);
const VERY_LONG_RANGES = new Set(["10y", "max"]);

/** Ranges "Key events" is disabled for — a bar's own event count doesn't
 * shrink as the range grows (a full trading history's worth of quarterly
 * earnings/analyst-rating actions all still fall somewhere on-screen), but
 * the number of *bars* they can spread across does, since every range
 * renders the same fixed plot width. Beyond 1Y, events land on so few
 * distinct bars that `positionedEvents`' same-bar stacking piles them into
 * dense, unreadable columns rather than a scattering of individual dots. */
const EVENTS_DISABLED_RANGES = new Set(["2y", "3y", "5y", "10y", "max"]);

function formatAxisDate(dateStr, rangeId) {
  const d = new Date(dateStr);
  if (VERY_LONG_RANGES.has(rangeId)) return d.toLocaleDateString(undefined, { year: "numeric" });
  if (LONG_RANGES.has(rangeId)) return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** `equicast_events.EventsClient`'s raw split `ratio` (e.g. `4.0` for a
 * 4-for-1 split, `0.5` for a 1-for-2 reverse split — see its own
 * docstring) as the "X-for-Y" form a split is normally described in,
 * whichever side of 1 it lands on. */
function formatSplitRatio(ratio) {
  return ratio >= 1 ? `${ratio}-for-1` : `1-for-${1 / ratio}`;
}

/** One event's own detail rows (date plus whatever `event_type`-specific
 * fields it carries) — shared by the single-event hover tooltip and the
 * merged-events modal below, so the two don't drift on what a "rating"
 * or "earnings" event actually shows. */
function EventDetailRows({ event, seriesCurrency, rangeId }) {
  return (
    <>
      <span className="ec-pchart-event-tooltip-row">
        <span>Date</span>
        <span>{formatAxisDate(event.date, rangeId)}</span>
      </span>
      {event.event_type === "earnings" && (
        <>
          <span className="ec-pchart-event-tooltip-row">
            <span>EPS Estimate</span>
            <span>{event.eps_estimate ?? "—"}</span>
          </span>
          <span className="ec-pchart-event-tooltip-row">
            <span>EPS Actual</span>
            <span>{event.reported_eps ?? "—"}</span>
          </span>
          <span className="ec-pchart-event-tooltip-row">
            <span>EPS Surprise</span>
            <span>{event.surprise_pct != null ? `${event.surprise_pct.toFixed(2)}%` : "—"}</span>
          </span>
        </>
      )}
      {event.event_type === "rating" && (
        <>
          <span className="ec-pchart-event-tooltip-row">
            <span>Analyst</span>
            <span>{event.firm ?? "—"}</span>
          </span>
          <span className="ec-pchart-event-tooltip-row">
            <span>Rating Action</span>
            <span>{event.action ?? "—"}</span>
          </span>
          <span className="ec-pchart-event-tooltip-row">
            <span>Rating</span>
            <span>{event.to_grade ?? "—"}</span>
          </span>
          {event.price_target_action != null && (
            <span className="ec-pchart-event-tooltip-row">
              <span>Price Action</span>
              <span>{event.price_target_action}</span>
            </span>
          )}
          {(event.current_price_target != null || event.prior_price_target != null) && (
            <span className="ec-pchart-event-tooltip-row">
              <span>Price Target</span>
              <span>
                {event.prior_price_target != null
                  ? formatPrice(event.prior_price_target, seriesCurrency)
                  : "—"}
                {" -> "}
                {event.current_price_target != null
                  ? formatPrice(event.current_price_target, seriesCurrency)
                  : "—"}
              </span>
            </span>
          )}
        </>
      )}
      {event.event_type === "split" && (
        <span className="ec-pchart-event-tooltip-row">
          <span>Ratio</span>
          <span>{formatSplitRatio(event.ratio)}</span>
        </span>
      )}
    </>
  );
}

/** Column defs per `event_type` — the same fields `EventDetailRows` shows
 * as label/value pairs for one event, reshaped as a table's columns so the
 * merged-events modal can lay several same-day events out as one row each
 * rather than repeating a full label/value block per event. */
const EVENT_TABLE_COLUMNS = {
  earnings: [
    { label: "EPS Estimate", render: (event) => event.eps_estimate ?? "—" },
    { label: "EPS Actual", render: (event) => event.reported_eps ?? "—" },
    {
      label: "EPS Surprise",
      render: (event) => (event.surprise_pct != null ? `${event.surprise_pct.toFixed(2)}%` : "—"),
    },
  ],
  rating: [
    { label: "Analyst", render: (event) => event.firm ?? "—" },
    { label: "Rating Action", render: (event) => event.action ?? "—" },
    { label: "Rating", render: (event) => event.to_grade ?? "—" },
    { label: "Price Action", render: (event) => event.price_target_action ?? "—" },
    {
      label: "Price Target",
      render: (event, seriesCurrency) => {
        if (event.current_price_target == null && event.prior_price_target == null) return "—";
        const prior =
          event.prior_price_target != null ? formatPrice(event.prior_price_target, seriesCurrency) : "—";
        const current =
          event.current_price_target != null ? formatPrice(event.current_price_target, seriesCurrency) : "—";
        return `${prior} -> ${current}`;
      },
    },
  ],
  split: [{ label: "Ratio", render: (event) => formatSplitRatio(event.ratio) }],
};

/** Every event in `events` shares the same `event_type` (they're grouped
 * that way — see `positionedEvents`), so one fixed column set applies to
 * the whole table. */
function EventDetailTable({ events, seriesCurrency }) {
  const columns = EVENT_TABLE_COLUMNS[events[0].event_type] ?? [];
  return (
    <table className="ec-pchart-event-table">
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column.label}>{column.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {events.map((event, i) => (
          <tr key={i}>
            {columns.map((column) => (
              <td key={column.label}>{column.render(event, seriesCurrency)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Y-axis tick label: a signed percentage in comparison (pctMode) charts,
 * the usual currency-formatted price otherwise. */
function formatYAxisLabel(value, pctMode, currency) {
  if (pctMode) return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
  return formatPrice(value, currency);
}

/** Evenly spaced bar indices to label on the x-axis — at most `maxTicks`,
 * always including the first and last bar. */
function axisTickIndices(count, maxTicks) {
  if (count <= 1) return [0].slice(0, count);
  const tickCount = Math.min(maxTicks, count);
  const indices = new Set();
  for (let i = 0; i < tickCount; i += 1) {
    indices.add(Math.round((i * (count - 1)) / (tickCount - 1)));
  }
  return [...indices].sort((a, b) => a - b);
}

// The SVG's viewBox width is tracked live (see the ResizeObserver effect
// below) so it always matches the element's real rendered pixel width —
// DEFAULT_WIDTH is only the value used for that one first render, before
// the observer has measured anything. HEIGHT matches ec-chart-svg's fixed
// CSS height exactly (see styles/chart.css) for the same reason: with
// both dimensions equal to the real box, preserveAspectRatio's default
// ("meet") scale factor is exactly 1 on both axes — no letterboxing (gaps
// down the sides) and no distortion (mismatched x/y scale stretching
// text/strokes), unlike either a mismatched fixed viewBox or a forced
// preserveAspectRatio="none" would produce.
const DEFAULT_WIDTH = 720;
const HEIGHT = 220;
const PADDING_TOP = 16;
const PADDING_RIGHT = 12;
const PADDING_BOTTOM = 28;
const PADDING_LEFT = 56;
const Y_AXIS_TICKS = 4;
const X_AXIS_MAX_TICKS = 6;

/**
 * The holding page's own price chart — same candle/line/area toggle, hover
 * tooltip and "compare against" overlay as accounts/PriceChart.jsx, but its
 * own subject series (`ticker`) is real data from GET .../prices/ (range
 * picker wired straight to the backend's `?range=`), not a synthetic random
 * walk. A comparison (picked via HoldingComparePicker, which can search any
 * stock/ETF/benchmark in the app's catalog, not just something the caller
 * already holds — including a real market-index benchmark like the S&P
 * 500) is real too — its own GET .../prices/ call for the same range.
 *
 * Once a comparison is active the chart switches from an absolute price
 * scale to a log-scaled "growth since range start" scale (0% baseline,
 * both positive and negative) instead of overlaying the two series on one
 * price axis. A plain price axis fails outright — a mega-cap stock's price
 * appreciation over a long range can dwarf a benchmark's by orders of
 * magnitude, flattening the benchmark into the bottom few pixels. A LINEAR
 * % axis doesn't fix it either: a holding up 325,992% (a ~3,260x multiple)
 * and a benchmark up "only" 5,585% (a ~57x multiple) are still a rounding
 * error apart on a scale that has to span 0 to 325,992. Log-scaling the
 * growth ratio (see mainLog/compareLog below) means equal vertical
 * distance represents equal *rate* of growth regardless of the starting
 * multiple, so both series stay visibly dynamic and can cross each other
 * throughout the whole range — same idea as a "log scale" toggle on any
 * real charting platform. The Line/Area/Candles toggle is hidden in this
 * mode — OHLC candles and an area fill don't carry meaning once everything
 * is normalized to two overlaid log-growth lines, so comparison mode is
 * always a plain line chart.
 *
 * Unlike PriceChart.jsx, this owns its own data fetching (re-fetching
 * whenever `rangeId` changes) rather than receiving pre-built bars as
 * props — same pattern TickerSearchField/CreatePortfolioDrawer already use
 * for a component that needs its own API calls.
 *
 * `avgPrice` (the caller's real weighted-average buy price for this
 * ticker, or null when there are no shares/no transactions) draws as a
 * grey dashed reference line, and is folded into the y-domain alongside
 * the series' own high/low so it stays on-screen even when it falls
 * outside the visible price range for the selected date range (e.g. a
 * short "5d" window whose price band sits well above/below where the
 * ticker was originally bought). `currentPrice` (the latest real market
 * price — marketProfile's day_close — or null when no market data is
 * published) draws the same way, in the accent info color instead of grey
 * so it reads as a distinct marker from the avg-price line whenever the
 * two are both on-screen and don't coincide with the series' own last bar.
 *
 * Picking a benchmark (not a holding/ticker) as the comparison also renders
 * HoldingBenchmarkRating below the chart — a real 0-100 rating derived
 * from both sides' `GET .../metrics/`, independent of this chart's own
 * range picker (see that component's docstring for the exact formula).
 *
 * Switching ranges doesn't blank the view while the new bars load: `series`
 * is left in place until the fetch resolves, so the previous range's chart
 * stays up (dimmed via "is-refreshing", styles/chart.css) rather than
 * flashing to a bare loading line. Once the new bars land, the main line
 * "draws" across the plot (stroke-dasharray/dashoffset, see mainLineRef's
 * effect) and the area fill/candles fade+rise in (`ec-chart-reveal`, keyed
 * on `revision` so it only replays when there's actually a new curve) —
 * the same reveal Yahoo Finance's own chart uses on a range change. The
 * avg-price/current-price reference lines get their own, different
 * treatment (HoldingPriceChart.css): a continuously flowing dash pattern —
 * avg-price right-to-left, current-price left-to-right, opposite
 * directions so the two read as distinct — rather than a one-shot reveal,
 * plus a `transition: y1, y2` so a change in their vertical position (a
 * range switch rescaling the y-domain, or the price itself changing) eases
 * there instead of jumping. The comparison/benchmark overlay line gets the
 * *same* draw-in as the main line instead (left-to-right), but via an
 * animated clip-path reveal rather than mainLineRef's stroke-dasharray
 * trick — that trick only works because the main line has no dash pattern
 * of its own to preserve; the compare line's real "4 3" dasharray would get
 * permanently flattened into one solid dash by it. See compareClipRectRef's
 * effect below.
 *
 * A "Key events" toggle (off by default, matching Yahoo Finance's own)
 * overlays real earnings/analyst-rating/stock-split markers from
 * `GET .../events/` — fetched lazily, only once switched on. Events
 * sharing the same date and `event_type` (e.g. several analysts revising
 * ratings the same day) collapse into one dot rather than one each, same
 * as Yahoo's own rendering — see `positionedEvents` below for the
 * grouping/layout math. Each dot pins to its nearest trading day's own bar
 * (see `barIndexForDate`) and draws a fixed offset above that bar's y
 * value, so markers track the curve's shape in both plain-price and
 * comparison (log-growth) mode; an event outside the chart's currently
 * visible date range is dropped rather than clamped to an edge. Hovering a
 * single-event dot shows its full details in a small floating tooltip
 * (`EventDetailRows`); hovering a merged dot shows a lightweight summary
 * instead, with the full per-event details behind a click into a modal —
 * a stack of five rating changes' full fields would overwhelm a hover
 * tooltip the way one event's never does.
 *
 * Disabled (see `EVENTS_DISABLED_RANGES`) for 2Y and every longer range —
 * a full trading history's worth of events still all lands somewhere
 * on-screen no matter the range, but the number of distinct bars they can
 * spread across shrinks as the range grows, so beyond 1Y they pile
 * into dense, unreadable columns rather than scattering into individual
 * dots. Switching to a disabled range while events are on turns them back
 * off automatically.
 *
 * @param {{ assetClass: string, ticker: string, currency: string|null, avgPrice?: number|null, currentPrice?: number|null }} props
 */
function HoldingPriceChart({ assetClass, ticker, currency, avgPrice = null, currentPrice = null }) {
  const api = useApi();
  const [chartType, setChartType] = useState("line");
  const [rangeId, setRangeId] = useState("max");
  const [compare, setCompare] = useState({ id: "", label: null, ticker: null, assetClass: null });
  const [hoverIndex, setHoverIndex] = useState(null);
  const svgRef = useRef(null);
  const mainLineRef = useRef(null);
  const compareClipId = useId();
  const compareClipRectRef = useRef(null);

  // Keeps the viewBox's width equal to the SVG's own real rendered width
  // (see DEFAULT_WIDTH's comment above) — measured on layout (before
  // paint, so there's no visible flash of the fallback width) and again on
  // every resize (a window resize, or the sidebar/page layout otherwise
  // changing this element's box).
  const [width, setWidth] = useState(DEFAULT_WIDTH);

  useLayoutEffect(() => {
    const el = svgRef.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const boxWidth = entries[0]?.contentRect.width;
      if (boxWidth) setWidth(boxWidth);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const [series, setSeries] = useState(null);
  const [status, setStatus] = useState("loading");

  // Bumped each time a fetch actually lands new bars — the reveal
  // animation (see mainLineRef's effect and ec-chart-reveal below) keys off
  // this rather than `rangeId` directly, so it only replays once there's
  // really a new curve to draw, not on every render in between.
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setHoverIndex(null);
    getPrices(api, assetClass, ticker, { range: rangeId })
      .then((result) => {
        if (cancelled) return;
        setSeries(result);
        setStatus(result.prices.length > 0 ? "ok" : "empty");
        setRevision((r) => r + 1);
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [api, assetClass, ticker, rangeId]);

  // `series` is deliberately left in place while a range switch is in
  // flight (nothing here clears it), so `bars` keeps rendering the
  // previous range's chart — dimmed via the "is-refreshing" class below —
  // right up until the new one lands, instead of the view blanking out to
  // a bare "Loading…" line every time a range button is clicked.
  const bars = useMemo(() => series?.prices ?? [], [series]);
  const hasData = bars.length > 0;
  const seriesCurrency = series?.currency ?? currency ?? null;

  // Off by default (matches Yahoo Finance's own "Key events" toggle) and
  // fetched lazily — only once switched on — rather than alongside `series`
  // above, so a viewer who never touches the toggle never pays for the
  // extra request. `events` stays `null` (not yet fetched) until the first
  // successful/failed fetch resolves; a 404 (nothing published for this
  // ticker yet) and any other failure both collapse to `[]` — same
  // "degrade to nothing shown, not an error message" forgiving treatment
  // HoldingTickerPage.jsx already gives getDividends. Re-fetches every time
  // the toggle flips back on rather than caching "already tried" in a ref —
  // cheap given getEvents' own same-day IndexedDB cache (see
  // utils/eventsCache.js), and simpler than tracking that separately.
  const [showEvents, setShowEvents] = useState(false);
  const [events, setEvents] = useState(null);
  const [hoveredEvent, setHoveredEvent] = useState(null);
  // Set only for a dot representing >1 grouped event (see `positionedEvents`
  // below) — a lightweight hover summary, distinct from `hoveredEvent`'s
  // full inline detail tooltip for a single-event dot.
  const [hoveredEventGroup, setHoveredEventGroup] = useState(null);
  // The grouped-events dot last clicked, whose full details are shown in a
  // modal (see `EventDetailRows`) rather than crowding the hover tooltip.
  const [openEventGroup, setOpenEventGroup] = useState(null);
  const eventsAllowed = !EVENTS_DISABLED_RANGES.has(rangeId);

  // Closes the merged-events tooltip on a short delay rather than
  // immediately on the dot's own mouseleave, so the cursor has time to
  // reach the tooltip's "Click for details" button (a separate, non-
  // overlapping element a few pixels away) before it unmounts — without
  // this, the tooltip would vanish mid-transit and the button could never
  // actually be clicked. Hovering either the dot or the tooltip itself
  // cancels the pending close.
  const eventGroupHideTimerRef = useRef(null);
  const cancelEventGroupHide = () => {
    if (eventGroupHideTimerRef.current !== null) {
      clearTimeout(eventGroupHideTimerRef.current);
      eventGroupHideTimerRef.current = null;
    }
  };
  const scheduleEventGroupHide = () => {
    cancelEventGroupHide();
    eventGroupHideTimerRef.current = setTimeout(() => setHoveredEventGroup(null), 200);
  };
  useEffect(() => cancelEventGroupHide, []);

  // Switching to a range Key events is disabled for turns it back off
  // (rather than just hiding the already-on toggle's dots) so flipping
  // back to an allowed range later starts from its normal off-by-default
  // state, not a stale "on" the viewer never actually chose there.
  useEffect(() => {
    if (!eventsAllowed && showEvents) {
      setShowEvents(false);
      setHoveredEvent(null);
      setHoveredEventGroup(null);
      setOpenEventGroup(null);
    }
  }, [eventsAllowed, showEvents]);

  useEffect(() => {
    if (!showEvents) return undefined;
    let cancelled = false;
    getEvents(api, assetClass, ticker)
      .then((result) => {
        if (!cancelled) setEvents(result.events);
      })
      .catch(() => {
        if (!cancelled) setEvents([]);
      });
    return () => {
      cancelled = true;
    };
  }, [api, assetClass, ticker, showEvents]);

  // Fetches the selected comparison's (a ticker or a benchmark, both carry
  // a real ticker/assetClass — see HoldingComparePicker) own real prices
  // for the same range; skipped entirely while nothing is selected yet
  // (compare.ticker/compare.assetClass still null).
  const [compareSeries, setCompareSeries] = useState(null);
  const [compareStatus, setCompareStatus] = useState("idle");

  useEffect(() => {
    if (!compare.ticker || !compare.assetClass) {
      setCompareSeries(null);
      setCompareStatus("idle");
      return undefined;
    }

    let cancelled = false;
    setCompareStatus("loading");
    getPrices(api, compare.assetClass, compare.ticker, { range: rangeId })
      .then((result) => {
        if (cancelled) return;
        setCompareSeries(result);
        setCompareStatus(result.prices.length > 0 ? "ok" : "empty");
      })
      .catch(() => {
        if (cancelled) return;
        setCompareStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [api, compare.ticker, compare.assetClass, rangeId]);

  const compareBars = useMemo(() => compareSeries?.prices ?? [], [compareSeries]);

  // A comparison is always shown as % change from its own first bar, on the
  // same 0%-baseline scale as the main series (see pctMode below) — so,
  // unlike a shared price axis, no rebasing to the main series' price level
  // is needed; each series just needs to be internally consistent. The two
  // series are still date-aligned (not just zipped by index) since
  // different tickers/exchanges don't always share the same trading
  // calendar — a compare date missing from the main series' bars forward-
  // fills from the last known compare close, same idea as a real trading
  // desk holding a stale price over a market holiday.
  const compareAlignedCloses = useMemo(() => {
    if (!compare.id || bars.length === 0) return null;
    if (compareStatus !== "ok" || compareBars.length === 0) return null;

    const closeByDate = new Map(compareBars.map((b) => [b.date, b.close]));
    let lastKnown = compareBars[0].close;
    return bars.map((b) => {
      if (closeByDate.has(b.date)) lastKnown = closeByDate.get(b.date);
      return lastKnown;
    });
  }, [compare.id, compareStatus, compareBars, bars]);

  // Comparison mode is driven purely by whether a comparison is selected —
  // it engages as soon as the picker makes a selection, before that
  // selection's own prices have even finished loading, so the axis doesn't
  // jump from price to % mid-flight once compareAlignedCloses resolves.
  const pctMode = Boolean(compare.id);

  // Growth ratio (close / first close) rather than a plain % difference —
  // this is what gets log-scaled below. A holding up 325,992% (a ~3,260x
  // multiple) and a benchmark up "only" 5,585% (a ~57x multiple) still look
  // like a rounding error apart on a LINEAR % axis, since the axis has to
  // span 0 to 325,992 — the smaller series flatlines near zero. Plotting
  // log(ratio) instead means equal vertical distance = equal *rate* of
  // growth (e.g. any doubling looks the same height, whether it's 3,260x
  // growing to 6,520x or 57x growing to 114x), so both series stay visibly
  // dynamic and can cross each other throughout the whole range.
  const mainRatio = useMemo(() => {
    if (bars.length === 0) return null;
    const first = bars[0].close;
    return bars.map((b) => b.close / first);
  }, [bars]);

  const compareRatio = useMemo(() => {
    if (!compareAlignedCloses) return null;
    const first = compareAlignedCloses[0];
    return compareAlignedCloses.map((c) => c / first);
  }, [compareAlignedCloses]);

  const avgRatio = useMemo(() => {
    if (avgPrice == null || bars.length === 0) return null;
    return avgPrice / bars[0].close;
  }, [avgPrice, bars]);

  const currentRatio = useMemo(() => {
    if (currentPrice == null || bars.length === 0) return null;
    return currentPrice / bars[0].close;
  }, [currentPrice, bars]);

  const mainLog = useMemo(() => (mainRatio ? mainRatio.map(Math.log) : null), [mainRatio]);
  const compareLog = useMemo(() => (compareRatio ? compareRatio.map(Math.log) : null), [compareRatio]);
  const avgLog = avgRatio != null ? Math.log(avgRatio) : null;
  const currentLog = currentRatio != null ? Math.log(currentRatio) : null;

  // The legend's total-change badges stay in plain (linear) %, since "up
  // 27,918%" reads naturally there — only the chart's own y-positions use
  // the log-scaled values above.
  const compareChangePct = compareRatio ? (compareRatio[compareRatio.length - 1] - 1) * 100 : null;

  const { min, max } = useMemo(() => {
    if (bars.length === 0) return { min: 0, max: 1 };
    if (pctMode) {
      const values = [...(mainLog ?? []), 0];
      if (compareLog) values.push(...compareLog);
      if (avgLog != null) values.push(avgLog);
      if (currentLog != null) values.push(currentLog);
      return { min: Math.min(...values), max: Math.max(...values) };
    }
    const values = bars.flatMap((b) => [b.high, b.low]);
    if (avgPrice != null) values.push(avgPrice);
    if (currentPrice != null) values.push(currentPrice);
    return { min: Math.min(...values), max: Math.max(...values) };
  }, [bars, pctMode, mainLog, compareLog, avgLog, avgPrice, currentLog, currentPrice]);

  const rangeSpan = max - min || 1;
  const plotWidth = width - PADDING_LEFT - PADDING_RIGHT;
  const plotHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const step = bars.length > 0 ? plotWidth / bars.length : plotWidth;

  const xFor = (i) => PADDING_LEFT + step * (i + 0.5);
  const yFor = (value) => PADDING_TOP + plotHeight * (1 - (value - min) / rangeSpan);
  const bottomY = PADDING_TOP + plotHeight;

  const linePath = bars.map((b, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(b.close)}`).join(" ");
  const areaPath = bars.length > 0 ? `${linePath} L${xFor(bars.length - 1)},${bottomY} L${xFor(0)},${bottomY} Z` : "";
  const pctLinePath = mainLog
    ? mainLog.map((v, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(v)}`).join(" ")
    : "";
  const comparePctPath = compareLog
    ? compareLog.map((v, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(v)}`).join(" ")
    : null;

  const first = bars[0];
  const last = bars[bars.length - 1];
  const changePct = first && last ? ((last.close - first.open) / first.open) * 100 : null;
  const isUp = (changePct ?? 0) >= 0;

  const handleMove = (event) => {
    if (!svgRef.current || bars.length === 0) return;
    const svg = svgRef.current;
    // Mapping clientX through getBoundingClientRect()'s width (a plain
    // pixel-ratio scale) assumes the viewBox fills that box exactly — true
    // here (viewBox width == the SVG's own live-measured width, see the
    // ResizeObserver effect above), but getScreenCTM() is the real
    // screen-pixel-to-viewBox transform regardless, so this stays correct
    // even for a stale `width` in the render this event fires during (the
    // observer callback and this handler aren't guaranteed to be in sync
    // on the exact same frame).
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const { x } = point.matrixTransform(svg.getScreenCTM().inverse());
    const index = Math.min(bars.length - 1, Math.max(0, Math.floor((x - PADDING_LEFT) / step)));
    setHoverIndex(index);
  };

  const hovered = hoverIndex !== null ? bars[hoverIndex] : last;
  const hoveredLabel = hovered ? formatAxisDate(hovered.date, rangeId) : null;

  const yTicks = Array.from({ length: Y_AXIS_TICKS + 1 }, (_, i) => {
    const value = max - (rangeSpan * i) / Y_AXIS_TICKS;
    return { key: i, value, y: yFor(value) };
  });
  const xTickIndices = axisTickIndices(bars.length, X_AXIS_MAX_TICKS);

  // Events sharing the same (date, event_type) — e.g. several analysts
  // revising ratings the same day — are grouped into a single dot rather
  // than one dot each, matching how Yahoo Finance's own "Key events"
  // renders a busy day as one marker rather than a stack. Each group is
  // pinned to its nearest bar's x position and drawn a fixed offset above
  // that bar's own y value (its log-growth ratio in pctMode, its close
  // price otherwise — the same value/scale `yFor` already maps everything
  // else on this chart through), so a marker tracks the curve's shape
  // rather than sitting on a flat row. Events off the visible range
  // (before the first bar, or after the last — a future-dated estimated
  // earnings date beyond "today") are dropped outright rather than
  // clamped to an edge bar, which would place them at a date they didn't
  // happen on. Multiple *groups* landing on the same bar (e.g. an
  // earnings report and a rating change the same day) still stack upward
  // from that bar's own offset rather than overlapping.
  const positionedEvents = [];
  if (showEvents && events && bars.length > 0) {
    const firstDate = bars[0].date;
    const lastDate = bars[bars.length - 1].date;
    const groupsByKey = new Map();
    for (const event of events) {
      if (event.date < firstDate || event.date > lastDate) continue;
      const index = barIndexForDate(bars, event.date);
      if (index === -1) continue;
      const key = `${event.date}|${event.event_type}`;
      let group = groupsByKey.get(key);
      if (!group) {
        group = { event_type: event.event_type, date: event.date, index, events: [] };
        groupsByKey.set(key, group);
      }
      group.events.push(event);
    }
    const stackCountByIndex = new Map();
    for (const group of groupsByKey.values()) {
      const stack = stackCountByIndex.get(group.index) ?? 0;
      stackCountByIndex.set(group.index, stack + 1);
      const baseValue = pctMode ? mainLog[group.index] : bars[group.index].close;
      positionedEvents.push({
        ...group,
        x: xFor(group.index),
        y: yFor(baseValue) - 14 - stack * 14,
      });
    }
  }

  // "Draws" the main line across the plot on every new revision (a range
  // switch, a ticker change, or the initial load) via the classic
  // stroke-dasharray/dashoffset reveal — set the offset back to the path's
  // full length with transitions off, force a reflow so the browser
  // registers that as the starting point, then hand off to CSS's own
  // `transition: stroke-dashoffset` (ec-chart-line, styles/chart.css) to
  // animate it back to 0. Left untouched under prefers-reduced-motion:
  // that media query just turns the CSS transition off, so the dashoffset
  // set here still resolves to 0, just without animating there.
  useLayoutEffect(() => {
    const el = mainLineRef.current;
    if (!el || typeof el.getTotalLength !== "function") return;
    let length;
    try {
      length = el.getTotalLength();
    } catch {
      return;
    }
    if (!length) return;
    el.style.transitionProperty = "none";
    el.style.strokeDasharray = `${length}`;
    el.style.strokeDashoffset = `${length}`;
    el.getBoundingClientRect();
    el.style.transitionProperty = "";
    el.style.strokeDashoffset = "0";
  }, [revision]);

  // Same left-to-right draw-in as the main line above, but via a growing
  // clip-path rect (0 -> plotWidth wide) rather than stroke-dasharray/
  // dashoffset — the compare line keeps a real "4 3" dasharray
  // (ec-pchart-compare-line, accounts/PriceChart.css) the whole time, this
  // just reveals progressively more of it, so the dash pattern itself is
  // never touched. Keyed on `comparePctPath` (the actual path data) rather
  // than `revision`, since the comparison's own fetch resolves on its own
  // schedule, independent of the main series'.
  useLayoutEffect(() => {
    const el = compareClipRectRef.current;
    if (!el) return;
    el.style.transitionProperty = "none";
    el.setAttribute("width", "0");
    el.getBoundingClientRect();
    el.style.transitionProperty = "";
    el.setAttribute("width", String(Math.max(plotWidth, 0)));
    // Deliberately excludes `plotWidth` — the <rect>'s `width` prop below
    // already tracks it declaratively on every render (a resize just
    // updates that attribute directly), so re-running this effect on
    // resize would only replay the reveal-from-0 animation for no reason.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comparePctPath]);

  return (
    <>
    <Card className="ec-pchart">
      <div className="ec-pchart-toolbar">
        {!pctMode && (
          <div className="ec-chart-toggle" role="group" aria-label="Chart type">
            {["line", "area", "candle"].map((type) => (
              <button
                key={type}
                type="button"
                className={`ec-chart-toggle-btn${chartType === type ? " is-active" : ""}`}
                onClick={() => setChartType(type)}
              >
                {type === "candle" ? "Candles" : type === "line" ? "Line" : "Area"}
              </button>
            ))}
          </div>
        )}

        <HoldingComparePicker
          currentTicker={ticker}
          compareId={compare.id}
          compareLabel={compare.label}
          onSelect={({ compareId, label, ticker: compareTicker, assetClass: compareAssetClass }) =>
            setCompare({ id: compareId, label, ticker: compareTicker, assetClass: compareAssetClass })
          }
          onClear={() => setCompare({ id: "", label: null, ticker: null, assetClass: null })}
        />
      </div>

      <div className="ec-pchart-ranges" role="group" aria-label="Date range">
        {RANGES.map((r) => (
          <button
            key={r.id}
            type="button"
            className={`ec-pchart-range-btn${r.id === rangeId ? " is-active" : ""}`}
            onClick={() => setRangeId(r.id)}
          >
            {r.label}
          </button>
        ))}
      </div>

      {status === "loading" && !hasData && <p className="ec-loading">Loading price history…</p>}
      {status === "error" && <p className="ec-chart-caption">Couldn&rsquo;t load price history for {ticker}.</p>}
      {status === "empty" && (
        <p className="ec-chart-caption">No price history published for {ticker} for this range yet.</p>
      )}

      {(status === "ok" || (status === "loading" && hasData)) && (
        <div className={`ec-pchart-chart${status === "loading" ? " is-refreshing" : ""}`}>
          <div className="ec-pchart-legend">
            <span className="ec-pchart-legend-item">
              <span className="ec-pchart-dot ec-pchart-dot--main" aria-hidden="true" />
              This holding
              {changePct !== null && (
                <span className={`ec-chart-change${isUp ? " is-up" : " is-down"}`}>
                  {isUp ? "▲" : "▼"} {Math.abs(changePct).toFixed(1)}%
                </span>
              )}
            </span>
            {compare.label && compareChangePct !== null && (
              <span className="ec-pchart-legend-item">
                <span className="ec-pchart-dot ec-pchart-dot--compare" aria-hidden="true" />
                {compare.label}
                <span className={`ec-chart-change${compareChangePct >= 0 ? " is-up" : " is-down"}`}>
                  {compareChangePct >= 0 ? "▲" : "▼"} {Math.abs(compareChangePct).toFixed(1)}%
                </span>
              </span>
            )}
            {avgPrice != null && (
              <span className="ec-pchart-legend-item">
                <span className="ec-pchart-swatch ec-pchart-swatch--avg" aria-hidden="true" />
                Avg buy price: <Balance>{formatPrice(avgPrice, seriesCurrency)}</Balance>
              </span>
            )}
            {currentPrice != null && (
              <span className="ec-pchart-legend-item">
                <span className="ec-pchart-swatch ec-pchart-swatch--current" aria-hidden="true" />
                Current price: <Balance>{formatPrice(currentPrice, seriesCurrency)}</Balance>
              </span>
            )}
          </div>

          <div className="ec-pchart-svg-wrap">
          <svg
            ref={svgRef}
            className="ec-chart-svg"
            viewBox={`0 0 ${width} ${HEIGHT}`}
            onMouseMove={handleMove}
            onMouseLeave={() => setHoverIndex(null)}
            role="img"
            aria-label={
              pctMode
                ? `Line chart of ${ticker}'s % change vs ${compare.label} for the ${rangeId} range`
                : `${chartType} chart of ${ticker}'s real price history for the ${rangeId} range`
            }
          >
            {yTicks.map(({ key, value, y }) => (
              <g key={key}>
                <line
                  x1={PADDING_LEFT}
                  x2={width - PADDING_RIGHT}
                  y1={y}
                  y2={y}
                  className="ec-chart-gridline"
                />
                <text
                  x={PADDING_LEFT - 8}
                  y={y}
                  className={`ec-chart-axis-label ec-chart-yaxis-label${pctMode ? "" : " ec-balance"}`}
                >
                  {pctMode
                    ? formatYAxisLabel((Math.exp(value) - 1) * 100, true, seriesCurrency)
                    : formatYAxisLabel(value, false, seriesCurrency)}
                </text>
              </g>
            ))}

            {xTickIndices.map((i) => (
              <text
                key={i}
                x={xFor(i)}
                y={HEIGHT - PADDING_BOTTOM + 18}
                className="ec-chart-axis-label ec-chart-xaxis-label"
              >
                {formatAxisDate(bars[i].date, rangeId)}
              </text>
            ))}

            {pctMode ? (
              <>
                <line
                  x1={PADDING_LEFT}
                  x2={width - PADDING_RIGHT}
                  y1={yFor(0)}
                  y2={yFor(0)}
                  className="ec-chart-zero-line"
                />
                <path ref={mainLineRef} d={pctLinePath} className="ec-chart-line" fill="none" />
                {comparePctPath && (
                  <>
                    <defs>
                      <clipPath id={compareClipId}>
                        <rect
                          ref={compareClipRectRef}
                          className="ec-chart-compare-clip"
                          x={PADDING_LEFT}
                          y={PADDING_TOP}
                          width={plotWidth}
                          height={plotHeight}
                        />
                      </clipPath>
                    </defs>
                    <path
                      d={comparePctPath}
                      className="ec-pchart-compare-line"
                      fill="none"
                      clipPath={`url(#${compareClipId})`}
                    />
                  </>
                )}
                {avgLog != null && (
                  <line
                    x1={PADDING_LEFT}
                    x2={width - PADDING_RIGHT}
                    y1={yFor(avgLog)}
                    y2={yFor(avgLog)}
                    className="ec-chart-avg-line"
                  />
                )}
                {currentLog != null && (
                  <line
                    x1={PADDING_LEFT}
                    x2={width - PADDING_RIGHT}
                    y1={yFor(currentLog)}
                    y2={yFor(currentLog)}
                    className="ec-chart-current-line"
                  />
                )}
              </>
            ) : (
              <>
                {chartType === "area" && (
                  <g className="ec-chart-reveal" key={revision}>
                    <path d={areaPath} className="ec-pchart-area" />
                  </g>
                )}
                {(chartType === "line" || chartType === "area") && (
                  <path ref={mainLineRef} d={linePath} className="ec-chart-line" fill="none" />
                )}
                {chartType === "candle" && (
                  <g className="ec-chart-reveal" key={revision}>
                    {bars.map((b, i) => (
                      <g key={b.date}>
                        <line
                          x1={xFor(i)}
                          x2={xFor(i)}
                          y1={yFor(b.high)}
                          y2={yFor(b.low)}
                          className={b.close >= b.open ? "ec-chart-wick-up" : "ec-chart-wick-down"}
                        />
                        <rect
                          x={xFor(i) - step * 0.3}
                          y={yFor(Math.max(b.open, b.close))}
                          width={step * 0.6}
                          height={Math.max(1.5, Math.abs(yFor(b.open) - yFor(b.close)))}
                          className={b.close >= b.open ? "ec-chart-candle-up" : "ec-chart-candle-down"}
                        />
                      </g>
                    ))}
                  </g>
                )}

                {avgPrice != null && (
                  <line
                    x1={PADDING_LEFT}
                    x2={width - PADDING_RIGHT}
                    y1={yFor(avgPrice)}
                    y2={yFor(avgPrice)}
                    className="ec-chart-avg-line"
                  />
                )}
                {currentPrice != null && (
                  <line
                    x1={PADDING_LEFT}
                    x2={width - PADDING_RIGHT}
                    y1={yFor(currentPrice)}
                    y2={yFor(currentPrice)}
                    className="ec-chart-current-line"
                  />
                )}
              </>
            )}

            {hoverIndex !== null && (
              <line
                x1={xFor(hoverIndex)}
                x2={xFor(hoverIndex)}
                y1={PADDING_TOP}
                y2={bottomY}
                className="ec-chart-crosshair"
              />
            )}

            {positionedEvents.map((group, i) => {
              const isGroup = group.events.length > 1;
              return (
                <circle
                  key={`${group.event_type}-${group.date}-${i}`}
                  cx={group.x}
                  cy={group.y}
                  r={5}
                  className={`ec-pchart-event-dot ec-pchart-event-dot--${group.event_type}`}
                  onMouseEnter={() => {
                    if (isGroup) {
                      cancelEventGroupHide();
                      setHoveredEventGroup(group);
                    } else {
                      setHoveredEvent({ event: group.events[0], x: group.x, y: group.y });
                    }
                  }}
                  onMouseLeave={() =>
                    isGroup
                      ? scheduleEventGroupHide()
                      : setHoveredEvent((current) =>
                          current?.event === group.events[0] ? null : current
                        )
                  }
                  onClick={isGroup ? () => setOpenEventGroup(group) : undefined}
                />
              );
            })}
          </svg>

          {hoveredEvent && (
            <div
              className="ec-pchart-event-tooltip"
              style={
                hoveredEvent.x > width / 2
                  ? { right: width - hoveredEvent.x + 10, top: Math.max(hoveredEvent.y - 8, 0) }
                  : { left: hoveredEvent.x + 10, top: Math.max(hoveredEvent.y - 8, 0) }
              }
            >
              <span className="ec-pchart-event-tooltip-title">
                <span
                  className={`ec-pchart-event-dot ec-pchart-event-dot--${hoveredEvent.event.event_type}`}
                  aria-hidden="true"
                />
                {EVENT_TYPE_META[hoveredEvent.event.event_type]?.label ?? hoveredEvent.event.event_type}
              </span>
              <EventDetailRows event={hoveredEvent.event} seriesCurrency={seriesCurrency} rangeId={rangeId} />
            </div>
          )}

          {hoveredEventGroup && (
            <div
              className="ec-pchart-event-tooltip ec-pchart-event-tooltip--light"
              style={
                hoveredEventGroup.x > width / 2
                  ? { right: width - hoveredEventGroup.x + 10, top: Math.max(hoveredEventGroup.y - 8, 0) }
                  : { left: hoveredEventGroup.x + 10, top: Math.max(hoveredEventGroup.y - 8, 0) }
              }
              onMouseEnter={cancelEventGroupHide}
              onMouseLeave={scheduleEventGroupHide}
            >
              <span className="ec-pchart-event-tooltip-title">
                <span
                  className={`ec-pchart-event-dot ec-pchart-event-dot--${hoveredEventGroup.event_type}`}
                  aria-hidden="true"
                />
                {EVENT_TYPE_META[hoveredEventGroup.event_type]?.label ?? hoveredEventGroup.event_type}
              </span>
              <span className="ec-pchart-event-tooltip-row">
                <span>Date</span>
                <span>{formatAxisDate(hoveredEventGroup.date, rangeId)}</span>
              </span>
              <span className="ec-pchart-event-tooltip-row">
                <span>Events</span>
                <span>{hoveredEventGroup.events.length}</span>
              </span>
              <button
                type="button"
                className="ec-pchart-event-tooltip-hint"
                onClick={() => {
                  cancelEventGroupHide();
                  setOpenEventGroup(hoveredEventGroup);
                  setHoveredEventGroup(null);
                }}
              >
                Click for details
              </button>
            </div>
          )}
          </div>

          {hovered && (
            <div className="ec-chart-tooltip">
              <span className="ec-chart-tooltip-date">{hoveredLabel}</span>
              <span>
                O <Balance>{formatPrice(hovered.open, seriesCurrency)}</Balance>
              </span>
              <span>
                H <Balance>{formatPrice(hovered.high, seriesCurrency)}</Balance>
              </span>
              <span>
                L <Balance>{formatPrice(hovered.low, seriesCurrency)}</Balance>
              </span>
              <span>
                C <Balance>{formatPrice(hovered.close, seriesCurrency)}</Balance>
              </span>
              <label
                className={`ec-pchart-events-toggle${eventsAllowed ? "" : " is-disabled"}`}
                title={eventsAllowed ? undefined : "Key events are only shown for 1Y, 6M, YTD, 1M and 1W ranges"}
              >
                <input
                  type="checkbox"
                  checked={showEvents}
                  disabled={!eventsAllowed}
                  onChange={(event) => {
                    setShowEvents(event.target.checked);
                    if (!event.target.checked) {
                      setHoveredEvent(null);
                      setHoveredEventGroup(null);
                      setOpenEventGroup(null);
                    }
                  }}
                />
                <span className="ec-pchart-events-toggle-track" aria-hidden="true" />
                Key events
              </label>
            </div>
          )}

          {compare.ticker && compareStatus === "loading" && (
            <p className="ec-chart-caption">Loading {compare.label}&rsquo;s price history…</p>
          )}
          {compare.ticker && (compareStatus === "error" || compareStatus === "empty") && (
            <p className="ec-chart-caption">
              No price history published for {compare.ticker} for this range yet.
            </p>
          )}

          {compare.assetClass === "benchmark" && (
            <HoldingBenchmarkRating
              assetClass={assetClass}
              ticker={ticker}
              benchmarkKey={compare.ticker}
              benchmarkLabel={compare.label}
            />
          )}
        </div>
      )}
    </Card>

    {openEventGroup && (
      <Modal
        open
        onClose={() => setOpenEventGroup(null)}
        title={`${EVENT_TYPE_META[openEventGroup.event_type]?.label ?? openEventGroup.event_type} — ${formatAxisDate(openEventGroup.date, rangeId)}`}
      >
        <div className="ec-pchart-event-modal">
          <EventDetailTable events={openEventGroup.events} seriesCurrency={seriesCurrency} />
        </div>
      </Modal>
    )}
    </>
  );
}

export default HoldingPriceChart;
