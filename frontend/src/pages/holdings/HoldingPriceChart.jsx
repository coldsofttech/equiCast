import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import Card from "../../components/core/Card.jsx";
import { useApi } from "../../api/useApi.js";
import { getPrices } from "../../api/market.js";
import { formatPrice } from "./holdingFinancials.js";
import HoldingBenchmarkRating from "./HoldingBenchmarkRating.jsx";
import HoldingComparePicker from "./HoldingComparePicker.jsx";
import "../accounts/PriceChart.css";
import "./HoldingPriceChart.css";

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

function formatAxisDate(dateStr, rangeId) {
  const d = new Date(dateStr);
  if (VERY_LONG_RANGES.has(rangeId)) return d.toLocaleDateString(undefined, { year: "numeric" });
  if (LONG_RANGES.has(rangeId)) return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
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
 * there instead of jumping.
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

  return (
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
                Avg buy price: {formatPrice(avgPrice, seriesCurrency)}
              </span>
            )}
            {currentPrice != null && (
              <span className="ec-pchart-legend-item">
                <span className="ec-pchart-swatch ec-pchart-swatch--current" aria-hidden="true" />
                Current price: {formatPrice(currentPrice, seriesCurrency)}
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
                <text x={PADDING_LEFT - 8} y={y} className="ec-chart-axis-label ec-chart-yaxis-label">
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
                {comparePctPath && <path d={comparePctPath} className="ec-pchart-compare-line" fill="none" />}
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
          </svg>

          {hovered && (
            <div className="ec-chart-tooltip">
              <span className="ec-chart-tooltip-date">{hoveredLabel}</span>
              <span>O {formatPrice(hovered.open, seriesCurrency)}</span>
              <span>H {formatPrice(hovered.high, seriesCurrency)}</span>
              <span>L {formatPrice(hovered.low, seriesCurrency)}</span>
              <span>C {formatPrice(hovered.close, seriesCurrency)}</span>
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
  );
}

export default HoldingPriceChart;
