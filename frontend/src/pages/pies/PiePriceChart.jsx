import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import Balance from "../../components/core/Balance.jsx";
import Card from "../../components/core/Card.jsx";
import { useApi } from "../../api/useApi.js";
import { getPrices } from "../../api/market.js";
import { resolveFxRate, formatPrice } from "../holdings/holdingFinancials.js";
import { RANGES, formatAxisDate, sliceForRange } from "../priceRangeSlicing.js";
import PieComparePicker from "./PieComparePicker.jsx";
import PieBenchmarkRating from "./PieBenchmarkRating.jsx";
import "../accounts/PriceChart.css";
import "../holdings/HoldingPriceChart.css";

/** Y-axis tick label: a signed percentage in comparison (pctMode) charts,
 * the usual currency-formatted value otherwise — same split
 * HoldingPriceChart's own formatYAxisLabel makes. */
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

// See HoldingPriceChart.jsx's identical constants for why width is tracked
// live via ResizeObserver and HEIGHT/DEFAULT_WIDTH match the SVG's real box.
const DEFAULT_WIDTH = 720;
const HEIGHT = 220;
const PADDING_TOP = 16;
const PADDING_RIGHT = 12;
const PADDING_BOTTOM = 28;
const PADDING_LEFT = 56;
const Y_AXIS_TICKS = 4;
const X_AXIS_MAX_TICKS = 6;

/** The most recent bar at or before `date` in `sortedBars` (ascending by
 * `date`, as `getPrices` already returns them), or `null` if `sortedBars`
 * has nothing that far back yet. */
function lastKnownBar(sortedBars, date) {
  let result = null;
  for (const bar of sortedBars) {
    if (bar.date > date) break;
    result = bar;
  }
  return result;
}

/**
 * Combines each holding's own real price series (already fetched, in
 * `targetCurrency`'s worth per share via `fxRate`) into one aggregate
 * portfolio-value curve: at every date across the union of every holding's
 * bar dates, values *today's* share count of each holding at that date's
 * own price — forward-filled (flat) from its last known bar when a holding
 * has no bar dated exactly that day, since different tickers don't always
 * share a trading calendar — and sums the results. A holding with no bar
 * that far back yet (its own history starts later than this date) is left
 * out of that date's total entirely rather than estimated.
 *
 * This is deliberately "what today's holdings would have been worth over
 * time," not a true historical-performance line — that would need a full
 * transaction-level position history to know what was actually held on
 * each past date, which this doesn't have.
 */
function buildAggregateBars(holdingSeries) {
  const dateSet = new Set();
  holdingSeries.forEach((h) => h.bars.forEach((b) => dateSet.add(b.date)));
  const dates = [...dateSet].sort();

  return dates
    .map((date) => {
      let open = 0;
      let high = 0;
      let low = 0;
      let close = 0;
      let hasData = false;
      holdingSeries.forEach((h) => {
        const exactBar = h.barsByDate.get(date);
        const bar = exactBar ?? lastKnownBar(h.bars, date);
        if (!bar) return;
        hasData = true;
        const weight = h.shares * h.fxRate;
        // A forward-filled holding only carries a flat close (no real
        // open/high/low for a date it has no bar on) — its contribution
        // to open/high/low is its own close, same as a candle with no
        // intraday range.
        open += weight * (exactBar ? bar.open : bar.close);
        high += weight * (exactBar ? bar.high : bar.close);
        low += weight * (exactBar ? bar.low : bar.close);
        close += weight * bar.close;
      });
      return hasData ? { date, open, high, low, close } : null;
    })
    .filter(Boolean);
}

/**
 * Fetches every held (`no_of_shares > 0`) holding's own real *full* price
 * history (the bundled `{daily, weekly, monthly}` payload — see
 * api/market.js's getPrices) once, resolving each to `targetCurrency` via a
 * single current FX rate (see resolveFxRate) — shared by the main pie
 * (PiePriceChart's own `holdings` prop) and a "compare against" pie
 * (fetched fresh via `getPie` once selected). A holding whose price/FX
 * can't be resolved is dropped rather than failing the whole fetch.
 * `targetCurrency` only has to be *some* consistent currency across the
 * holdings it's aggregating — for a compare pie, its choice doesn't affect
 * the % growth ratio the comparison actually plots (a constant FX rate
 * cancels out of a ratio), so the caller doesn't need the compare pie's own
 * default currency, just any one currency.
 *
 * Deliberately *not* range-scoped (no `rangeId` param) — unlike the old
 * per-range fetch this replaces, every held holding's full history is
 * fetched once regardless of which range is selected; `sliceAndAggregate`
 * below does the range-scoping client-side on every range-picker click,
 * with no further request (GitHub issue #150) — the previous version of
 * this function re-fetched every held holding on every range click, which
 * is the single biggest source of the extra API hits issue #150 flagged.
 */
async function fetchHoldingHistories(api, holdings, targetCurrency) {
  const heldHoldings = holdings.filter((h) => Number(h.no_of_shares) > 0);
  if (heldHoldings.length === 0) return [];

  const results = await Promise.all(
    heldHoldings.map(async (holding) => {
      try {
        const history = await getPrices(api, holding.asset_class, holding.ticker);
        if (history.daily.length === 0 && history.weekly.length === 0 && history.monthly.length === 0) {
          return null;
        }
        const fxRate = await resolveFxRate(api, history.currency, targetCurrency);
        if (fxRate == null) return null;
        return { shares: Number(holding.no_of_shares), fxRate, history };
      } catch {
        return null;
      }
    })
  );

  return results.filter(Boolean);
}

/**
 * Slices each of `holdingHistories`' full price history down to `rangeId`
 * (via `sliceForRange`) and combines the results with `buildAggregateBars`
 * — the client-side, synchronous counterpart to the network fetch
 * `fetchHoldingHistories` does once; called again on every range-picker
 * click with no further request.
 */
function sliceAndAggregate(holdingHistories, rangeId) {
  const holdingSeries = holdingHistories.map(({ shares, fxRate, history }) => {
    const bars = sliceForRange(history, rangeId);
    return { shares, fxRate, bars, barsByDate: new Map(bars.map((b) => [b.date, b])) };
  });
  return holdingSeries.length > 0 ? buildAggregateBars(holdingSeries) : [];
}

/**
 * PieDetailPage's/AccountDetailPage's aggregate price chart — same real
 * range picker, hover tooltip and "compare against" overlay as
 * HoldingPriceChart.jsx, but its own subject series is every one of
 * `holdings` combined into one aggregate value curve (see
 * buildAggregateBars) rather than a single ticker's own price. `holdings`
 * is one pie's own holdings for PieDetailPage, or an account's full direct
 * + pie-nested set for AccountDetailPage — this component has no pie- or
 * account-specific logic of its own; `entityLabel` (used in on-screen copy)
 * and the compare-related props below are what the caller supplies to
 * distinguish itself. There's no Candles chart type: unlike one ticker's
 * own real daily OHLC bar, an aggregate's per-date open/high/low is itself
 * a value-weighted sum across holdings' own bars, not a real traded range,
 * so rendering it as a candle would imply a precision the underlying
 * number doesn't have. Line/Area are the only two types.
 *
 * The "Compare against" control (PieComparePicker) reuses HoldingComparePicker's
 * own visual styling (same CSS classes/collapsed-trigger/open-panel/selected-
 * chip states) but is deliberately narrower in content: only `compareItems`
 * (this pie's sibling portfolios, or this account's sibling accounts —
 * already fetched by the caller) or a real benchmark (the same curated set
 * HoldingComparePicker offers as quick-picks, see BENCHMARKS) — no
 * free-text stock/ETF/fx search, since comparing an aggregate against one
 * arbitrary ticker isn't a meaningful comparison the way it is for a single
 * holding. Picking a `compareItems` entry calls the caller's own
 * `fetchCompareHoldings(refId)` (a pie's own holdings, or an account's full
 * direct + pie-nested set) and re-runs the exact same `fetchAggregateBars`
 * pipeline against them; picking a benchmark just fetches its own real
 * price series. Once a comparison is active the chart switches to a
 * log-scaled "growth since range start" % axis, exactly like
 * HoldingPriceChart's own pctMode (see that component's docstring for why
 * log-scaling, not a plain linear %, is what keeps two very different-sized
 * curves both visibly dynamic) — the chart-type toggle hides in this mode
 * for the same reason it does there. Picking a benchmark specifically also
 * renders PieBenchmarkRating below the chart — a real 0-100 rating of
 * `holdings`' own current-value-weighted metrics against the benchmark's,
 * independent of this chart's own range picker, same as HoldingPriceChart's
 * own HoldingBenchmarkRating.
 *
 * `investedTotal`/`currentValueTotal` (the caller's own `totals.invested`/
 * `totals.currentValue`, both in `currency`) draw as reference lines (grey
 * dashed / accent info dashed respectively) the same way HoldingPriceChart
 * treats avg buy price/current price — including in pctMode, log-scaled via
 * their own ratio to the first bar's close, so they stay meaningful and
 * on-screen even while comparing. They get the same continuously-flowing
 * dash animation too (ec-chart-avg-line/ec-chart-current-line,
 * HoldingPriceChart.css — already imported here, so no extra CSS needed).
 *
 * A holdings-set change doesn't blank the view while the new fetch is in
 * flight (a range switch has no such gap any more — see
 * `fetchHoldingHistories`/`sliceAndAggregate` above, GitHub issue #150):
 * the previous chart stays up, dimmed via "is-refreshing", same as
 * HoldingPriceChart.jsx (see that component's docstring for the full
 * reasoning, including why the "draws in left-to-right"/"fades+rises in"
 * reveal itself is reserved for this entity's genuine first paint only,
 * not a same-entity range switch — replaying it there used to make the
 * chart flash invisible for a frame right as the dim lifted, GitHub issue
 * #137). The compare/benchmark overlay's own clip-path draw-in is
 * unaffected either way, since it's keyed on the compare path itself, not
 * `revision`. This just ports the same mainLineRef/revision/
 * compareClipRectRef mechanics since PiePriceChart has its own separate
 * fetch effect and JSX, not anything HoldingPriceChart's CSS import alone
 * could cover. No candle-reveal case, since this chart has no Candles type.
 *
 * @param {{ holdings: import("../../api/accounts.js").Holding[], currency: string, entityLabel?: string, compareItems?: { id: string, name: string }[], compareItemType?: "pie"|"account", fetchCompareHoldings: (refId: string) => Promise<import("../../api/accounts.js").Holding[]>, investedTotal?: number|null, currentValueTotal?: number|null, holdingValuations?: { currentValue: number }[]|null }} props
 */
function PiePriceChart({
  holdings,
  currency,
  entityLabel = "portfolio",
  compareItems = [],
  compareItemType = "pie",
  fetchCompareHoldings,
  investedTotal = null,
  currentValueTotal = null,
  holdingValuations = null,
}) {
  const api = useApi();
  const [chartType, setChartType] = useState("line");
  const [rangeId, setRangeId] = useState("max");
  const [hoverIndex, setHoverIndex] = useState(null);
  const svgRef = useRef(null);
  const mainLineRef = useRef(null);
  const compareClipId = useId();
  const compareClipRectRef = useRef(null);
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

  const [holdingHistories, setHoldingHistories] = useState([]);
  const [status, setStatus] = useState("loading");

  // Bumped only for this entity's genuine first paint, mirroring
  // HoldingPriceChart's own `revision` fix for GitHub issue #137 — a
  // same-entity range switch (already kept smooth via the previous
  // chart staying up, dimmed by "is-refreshing") shouldn't also replay
  // the "start from nothing" reveal (mainLineRef's effect and
  // ec-chart-reveal below), which made the chart flash fully invisible
  // for a frame right as the dim was lifting — a blink, not the intended
  // smooth update. `holdings` gets a new array identity on most renders
  // of the caller even for the *same* pie/account (see
  // DiversificationChart.jsx's own signature fix for the identical
  // problem), so "did the entity actually change" is judged by a
  // content signature (sorted tickers), not `holdings`' own reference.
  const [revision, setRevision] = useState(0);
  const holdingsSignature = holdings
    .map((h) => h.ticker)
    .sort()
    .join("|");
  const prevEntityRef = useRef({ holdingsSignature: null, currency: null });

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setHoverIndex(null);
    fetchHoldingHistories(api, holdings, currency).then((result) => {
      if (cancelled) return;
      setHoldingHistories(result);
      setStatus("ok");
      const isSameEntity =
        prevEntityRef.current.holdingsSignature === holdingsSignature &&
        prevEntityRef.current.currency === currency;
      prevEntityRef.current = { holdingsSignature, currency };
      if (!isSameEntity) setRevision((r) => r + 1);
    });
    return () => {
      cancelled = true;
    };
  }, [api, holdings, currency, holdingsSignature]);

  // Nothing above clears `holdingHistories` while a new fetch is in
  // flight, so `bars` keeps reflecting the previous holdings set right up
  // until the new one lands — see the "is-refreshing" wrapper below. A
  // range switch has no such gap at all: slicing/aggregating client-side
  // (sliceAndAggregate) is synchronous.
  const bars = useMemo(
    () => sliceAndAggregate(holdingHistories, rangeId),
    [holdingHistories, rangeId]
  );
  const hasData = bars.length > 0;

  const [compare, setCompare] = useState({ id: "", type: null, refId: null, label: null });
  const [compareData, setCompareData] = useState(null);
  const [compareStatus, setCompareStatus] = useState("idle");

  useEffect(() => {
    if (!compare.id) {
      setCompareData(null);
      setCompareStatus("idle");
      return undefined;
    }

    let cancelled = false;
    setCompareStatus("loading");

    const load =
      compare.type === "benchmark"
        ? getPrices(api, "benchmark", compare.refId).then((history) => ({ type: "benchmark", history }))
        : fetchCompareHoldings(compare.refId)
            .then((h) => fetchHoldingHistories(api, h, currency))
            .then((holdingHistories) => ({ type: "holdings", holdingHistories }));

    load
      .then((result) => {
        if (cancelled) return;
        setCompareData(result);
        setCompareStatus("ok");
      })
      .catch(() => {
        if (cancelled) return;
        setCompareStatus("error");
      });

    return () => {
      cancelled = true;
    };
  }, [api, compare.id, compare.type, compare.refId, currency, fetchCompareHoldings]);

  const compareBars = useMemo(() => {
    if (!compareData) return null;
    return compareData.type === "benchmark"
      ? sliceForRange(compareData.history, rangeId)
      : sliceAndAggregate(compareData.holdingHistories, rangeId);
  }, [compareData, rangeId]);

  const handleCompareClear = () => setCompare({ id: "", type: null, refId: null, label: null });

  // A comparison is always shown as % change from its own first bar, on the
  // same 0%-baseline scale as the main series — each series just needs to
  // be internally consistent, no rebasing to the main series' own value
  // level is needed. The two series are still date-aligned (not just zipped
  // by index) since a compare pie/benchmark doesn't necessarily share this
  // pie's exact bar dates — a missing date forward-fills from the last
  // known compare close, same idea as a real trading desk holding a stale
  // price over a market holiday.
  const compareAlignedCloses = useMemo(() => {
    if (!compare.id || bars.length === 0) return null;
    if (compareStatus !== "ok" || !compareBars || compareBars.length === 0) return null;

    const closeByDate = new Map(compareBars.map((b) => [b.date, b.close]));
    let lastKnown = compareBars[0].close;
    return bars.map((b) => {
      if (closeByDate.has(b.date)) lastKnown = closeByDate.get(b.date);
      return lastKnown;
    });
  }, [compare.id, compareStatus, compareBars, bars]);

  const pctMode = Boolean(compare.id);

  // Growth ratio (close / first close), then log-scaled — see
  // HoldingPriceChart.jsx's own mainRatio/mainLog for the full reasoning
  // (equal vertical distance = equal *rate* of growth regardless of
  // starting multiple, so both series stay visibly dynamic together).
  const mainRatio = useMemo(() => {
    if (bars.length === 0) return null;
    const firstClose = bars[0].close;
    return bars.map((b) => b.close / firstClose);
  }, [bars]);

  const compareRatio = useMemo(() => {
    if (!compareAlignedCloses) return null;
    const first = compareAlignedCloses[0];
    return compareAlignedCloses.map((c) => c / first);
  }, [compareAlignedCloses]);

  const investedRatio = useMemo(() => {
    if (investedTotal == null || bars.length === 0) return null;
    return investedTotal / bars[0].close;
  }, [investedTotal, bars]);

  const currentValueRatio = useMemo(() => {
    if (currentValueTotal == null || bars.length === 0) return null;
    return currentValueTotal / bars[0].close;
  }, [currentValueTotal, bars]);

  const mainLog = useMemo(() => (mainRatio ? mainRatio.map(Math.log) : null), [mainRatio]);
  const compareLog = useMemo(() => (compareRatio ? compareRatio.map(Math.log) : null), [compareRatio]);
  const investedLog = investedRatio != null ? Math.log(investedRatio) : null;
  const currentValueLog = currentValueRatio != null ? Math.log(currentValueRatio) : null;

  // The legend's total-change badge stays in plain (linear) %, since "up
  // 27,918%" reads naturally there — only the chart's own y-positions use
  // the log-scaled values above.
  const compareChangePct = compareRatio ? (compareRatio[compareRatio.length - 1] - 1) * 100 : null;

  const { min, max } = useMemo(() => {
    if (bars.length === 0) return { min: 0, max: 1 };
    if (pctMode) {
      const values = [...(mainLog ?? []), 0];
      if (compareLog) values.push(...compareLog);
      if (investedLog != null) values.push(investedLog);
      if (currentValueLog != null) values.push(currentValueLog);
      return { min: Math.min(...values), max: Math.max(...values) };
    }
    const values = bars.flatMap((b) => [b.high, b.low]);
    if (investedTotal != null) values.push(investedTotal);
    if (currentValueTotal != null) values.push(currentValueTotal);
    return { min: Math.min(...values), max: Math.max(...values) };
  }, [bars, pctMode, mainLog, compareLog, investedLog, investedTotal, currentValueLog, currentValueTotal]);

  const rangeSpan = max - min || 1;
  const plotWidth = width - PADDING_LEFT - PADDING_RIGHT;
  const plotHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const step = bars.length > 0 ? plotWidth / bars.length : plotWidth;

  const xFor = (i) => PADDING_LEFT + step * (i + 0.5);
  const yFor = (value) => PADDING_TOP + plotHeight * (1 - (value - min) / rangeSpan);
  const bottomY = PADDING_TOP + plotHeight;

  const linePath = bars.map((b, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(b.close)}`).join(" ");
  const areaPath =
    bars.length > 0 ? `${linePath} L${xFor(bars.length - 1)},${bottomY} L${xFor(0)},${bottomY} Z` : "";
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

  // "Draws" the main line across the plot on every new revision — see
  // HoldingPriceChart.jsx's identical effect for the full reasoning
  // (stroke-dasharray/dashoffset, handed off to CSS's `transition:
  // stroke-dashoffset` on .ec-chart-line, styles/chart.css).
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

  // Same left-to-right draw-in for the compare/benchmark overlay as
  // HoldingPriceChart.jsx's own compareClipRectRef effect — a growing
  // clip-path rect rather than mainLineRef's stroke-dasharray trick, since
  // this line keeps a real dasharray (.ec-pchart-compare-line,
  // accounts/PriceChart.css) that trick would otherwise flatten.
  useLayoutEffect(() => {
    const el = compareClipRectRef.current;
    if (!el) return;
    el.style.transitionProperty = "none";
    el.setAttribute("width", "0");
    el.getBoundingClientRect();
    el.style.transitionProperty = "";
    el.setAttribute("width", String(Math.max(plotWidth, 0)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comparePctPath]);

  return (
    <Card className="ec-pchart">
      <div className="ec-pchart-toolbar">
        {!pctMode && (
          <div className="ec-chart-toggle" role="group" aria-label="Chart type">
            {["line", "area"].map((type) => (
              <button
                key={type}
                type="button"
                className={`ec-chart-toggle-btn${chartType === type ? " is-active" : ""}`}
                onClick={() => setChartType(type)}
              >
                {type === "line" ? "Line" : "Area"}
              </button>
            ))}
          </div>
        )}

        <PieComparePicker
          items={compareItems}
          itemType={compareItemType}
          compareId={compare.id}
          compareLabel={compare.label}
          onSelect={setCompare}
          onClear={handleCompareClear}
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
      {status === "ok" && !hasData && (
        <p className="ec-chart-caption">
          No price history to chart yet — this needs at least one holding with shares and published
          price/FX data.
        </p>
      )}

      {hasData && (
        <div className={`ec-pchart-chart${status === "loading" ? " is-refreshing" : ""}`}>
          <div className="ec-pchart-legend">
            <span className="ec-pchart-legend-item">
              <span className="ec-pchart-dot ec-pchart-dot--main" aria-hidden="true" />
              This {entityLabel}
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
            {investedTotal != null && (
              <span className="ec-pchart-legend-item">
                <span className="ec-pchart-swatch ec-pchart-swatch--avg" aria-hidden="true" />
                Total invested: <Balance>{formatPrice(investedTotal, currency)}</Balance>
              </span>
            )}
            {currentValueTotal != null && (
              <span className="ec-pchart-legend-item">
                <span className="ec-pchart-swatch ec-pchart-swatch--current" aria-hidden="true" />
                Current value: <Balance>{formatPrice(currentValueTotal, currency)}</Balance>
              </span>
            )}
          </div>

          <svg
            ref={svgRef}
            className="ec-chart-svg"
            viewBox={`0 0 ${width} ${HEIGHT}`}
            onMouseMove={handleMove}
            onMouseLeave={() => setHoverIndex(null)}
            role="img"
            aria-label={
              pctMode
                ? `Line chart of this ${entityLabel}'s % change vs ${compare.label} for the ${rangeId} range`
                : `${chartType} chart of this ${entityLabel}'s aggregate value for the ${rangeId} range`
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
                    ? formatYAxisLabel((Math.exp(value) - 1) * 100, true, currency)
                    : formatYAxisLabel(value, false, currency)}
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
                {investedLog != null && (
                  <line
                    x1={PADDING_LEFT}
                    x2={width - PADDING_RIGHT}
                    y1={yFor(investedLog)}
                    y2={yFor(investedLog)}
                    className="ec-chart-avg-line"
                  />
                )}
                {currentValueLog != null && (
                  <line
                    x1={PADDING_LEFT}
                    x2={width - PADDING_RIGHT}
                    y1={yFor(currentValueLog)}
                    y2={yFor(currentValueLog)}
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
                <path ref={mainLineRef} d={linePath} className="ec-chart-line" fill="none" />
                {investedTotal != null && (
                  <line
                    x1={PADDING_LEFT}
                    x2={width - PADDING_RIGHT}
                    y1={yFor(investedTotal)}
                    y2={yFor(investedTotal)}
                    className="ec-chart-avg-line"
                  />
                )}
                {currentValueTotal != null && (
                  <line
                    x1={PADDING_LEFT}
                    x2={width - PADDING_RIGHT}
                    y1={yFor(currentValueTotal)}
                    y2={yFor(currentValueTotal)}
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
          </svg>

          {hovered && (
            <div className="ec-chart-tooltip">
              <span className="ec-chart-tooltip-date">{hoveredLabel}</span>
              <span>
                O <Balance>{formatPrice(hovered.open, currency)}</Balance>
              </span>
              <span>
                H <Balance>{formatPrice(hovered.high, currency)}</Balance>
              </span>
              <span>
                L <Balance>{formatPrice(hovered.low, currency)}</Balance>
              </span>
              <span>
                C <Balance>{formatPrice(hovered.close, currency)}</Balance>
              </span>
            </div>
          )}

          {compare.id && compareStatus === "loading" && (
            <p className="ec-chart-caption">Loading {compare.label}&rsquo;s price history…</p>
          )}
          {compare.id &&
            (compareStatus === "error" || (compareStatus === "ok" && (!compareBars || compareBars.length === 0))) && (
              <p className="ec-chart-caption">
                No price history published for {compare.label} for this range yet.
              </p>
            )}

          {compare.type === "benchmark" && holdingValuations && (
            <PieBenchmarkRating
              holdings={holdings}
              valuations={holdingValuations}
              benchmarkKey={compare.refId}
              benchmarkLabel={compare.label}
              label={entityLabel}
            />
          )}
        </div>
      )}
    </Card>
  );
}

export default PiePriceChart;
