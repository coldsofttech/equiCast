import { useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import Balance from "../../components/core/Balance.jsx";
import {
  DIVIDEND_HISTORY_RANGES,
  UPCOMING_DIVIDEND_RANGES,
  availableForecastRanges,
  availablePastRanges,
  formatPrice,
  selectDividendHistory,
  selectUpcomingDividendsInRange,
} from "./holdingFinancials.js";
import "../accounts/PriceChart.css";
import "./HoldingPriceChart.css";

const DEFAULT_WIDTH = 720;
const HEIGHT = 220;
const PADDING_TOP = 16;
const PADDING_RIGHT = 12;
const PADDING_BOTTOM = 28;
const PADDING_LEFT = 56;
const Y_AXIS_TICKS = 4;
const X_AXIS_MAX_TICKS = 6;

/** A point's date span past which the x-axis switches to a coarser
 * "Mon YY"/"YYYY" label — mirrors priceRangeSlicing.js's LONG_RANGES/
 * VERY_LONG_RANGES, just computed from the plotted points' actual span
 * rather than a range id, since this chart's combined history+forecast
 * span isn't one of that picker's own ids. */
function axisFormat(spanDays) {
  if (spanDays > 365 * 6) return { year: "numeric" };
  if (spanDays > 500) return { month: "short", year: "2-digit" };
  return { month: "short", day: "numeric" };
}

function formatAxisDate(dateStr, spanDays) {
  return new Date(dateStr).toLocaleDateString(undefined, axisFormat(spanDays));
}

/** Evenly spaced point indices to label on the x-axis — at most
 * `maxTicks`, always including the first and last point. */
function axisTickIndices(count, maxTicks) {
  if (count <= 1) return [0].slice(0, count);
  const tickCount = Math.min(maxTicks, count);
  const indices = new Set();
  for (let i = 0; i < tickCount; i += 1) {
    indices.add(Math.round((i * (count - 1)) / (tickCount - 1)));
  }
  return [...indices].sort((a, b) => a - b);
}

const STATUS_LABEL = { paid: "Paid", declared: "Declared", estimated: "Estimated" };

/**
 * The "See all" drawer's dividend chart — a line/area series (no candles;
 * a discrete per-payout series has no open/high/low to plot) sharing
 * HoldingPriceChart's own look, controls and reveal animation (responsive
 * width via ResizeObserver, a Line/Area toggle, a range picker, a
 * stroke-dasharray "draw in" on first paint/every range change, a
 * always-shown hover tooltip defaulting to the latest point) rather than
 * HoldingDividendBarChart's bespoke bar rendering.
 *
 * The history side's start date depends on ownership: `ownFirstDividendDate`
 * (this position's own earliest recorded DIVIDEND transaction, passed by
 * the caller only when the holding is owned) anchors it to "since you
 * started receiving payouts"; `null` (not owned) falls back to the
 * ticker's own earliest paid record instead, so an unowned ticker still
 * shows real history. Either way, `availablePastRanges` hides any preset
 * range that wouldn't show anything narrower than what's already visible
 * (e.g. no point offering "10Y" when the real history/position is only 3
 * years old) — always leaving at least one.
 *
 * "Show forecast" (styled like HoldingPriceChart's own "Key events"
 * toggle, in the toolbar next to the Line/Area buttons) extends the
 * plotted series with declared/estimated records past today, in a
 * distinct dashed color (`ec-pchart-compare-line`, the same purple/dashed
 * treatment the price chart's own comparison overlay uses for its line —
 * plus a matching soft-purple area fill, `ec-pchart-forecast-area`, when
 * `chartType` is "area", so the forecast segment respects the same
 * chart-type toggle the historical segment does instead of always
 * rendering as a line) continuing from the last real historical point
 * rather than a disconnected second series. Toggling it on reveals a
 * second range picker (`availableForecastRanges`, symmetric to the past
 * side) for how far forward to project — independent of the past-side
 * range, since "how far back" and "how far forward" are different
 * questions.
 *
 * Every value plotted/labeled is in `displayCurrency` — `defaultCurrency`
 * once `fxRate` has resolved and differs from `currency` (native), with
 * the native figure kept in the hover tooltip alongside it; native-only
 * otherwise, same fallback `DividendCard` uses.
 *
 * @param {{
 *   dividends: import("../../api/market.js").DividendRecord[],
 *   currency: string|null,
 *   defaultCurrency: string|null,
 *   fxRate: number|null,
 *   ownFirstDividendDate: string|null,
 * }} props
 */
function HoldingDividendChart({ dividends, currency, defaultCurrency, fxRate, ownFirstDividendDate }) {
  const [chartType, setChartType] = useState("line");
  const [showForecast, setShowForecast] = useState(false);
  const [hoverIndex, setHoverIndex] = useState(null);
  const svgRef = useRef(null);
  const mainLineRef = useRef(null);
  const forecastClipRectRef = useRef(null);
  const forecastClipId = useId();

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

  const tickerFirstPaidDate = useMemo(() => {
    const paidDates = dividends.filter((d) => d.status === "paid").map((d) => d.ex_dividend_date);
    return paidDates.length > 0 ? paidDates.reduce((a, b) => (a < b ? a : b)) : null;
  }, [dividends]);
  const earliestDate = ownFirstDividendDate ?? tickerFirstPaidDate;

  const latestForecastDate = useMemo(() => {
    const dates = dividends.filter((d) => d.status !== "paid").map((d) => d.ex_dividend_date);
    return dates.length > 0 ? dates.reduce((a, b) => (a > b ? a : b)) : null;
  }, [dividends]);

  const pastRanges = useMemo(() => availablePastRanges(earliestDate), [earliestDate]);
  const forecastRanges = useMemo(
    () => availableForecastRanges(latestForecastDate),
    [latestForecastDate]
  );

  const [pastRangeId, setPastRangeId] = useState(
    () => DIVIDEND_HISTORY_RANGES[DIVIDEND_HISTORY_RANGES.length - 1].id
  );
  const [forecastRangeId, setForecastRangeId] = useState(
    () => UPCOMING_DIVIDEND_RANGES[UPCOMING_DIVIDEND_RANGES.length - 1].id
  );
  const effectivePastRangeId = pastRanges.some((r) => r.id === pastRangeId)
    ? pastRangeId
    : pastRanges[pastRanges.length - 1].id;
  const effectiveForecastRangeId = forecastRanges.some((r) => r.id === forecastRangeId)
    ? forecastRangeId
    : forecastRanges[forecastRanges.length - 1].id;

  // Bumped on every user-initiated control change (range/forecast/chart
  // type) so the reveal animations below replay the same "draw in" a first
  // paint gets — mirrors HoldingPriceChart's own `revision`/
  // `handleRangeChange` pattern.
  const [revision, setRevision] = useState(0);
  const bump = (setter) => (value) => {
    setter(value);
    setRevision((r) => r + 1);
  };

  const historyRecords = useMemo(
    () => selectDividendHistory(dividends, effectivePastRangeId, ownFirstDividendDate),
    [dividends, effectivePastRangeId, ownFirstDividendDate]
  );
  const forecastRecords = useMemo(
    () =>
      showForecast ? selectUpcomingDividendsInRange(dividends, effectiveForecastRangeId) : [],
    [dividends, showForecast, effectiveForecastRangeId]
  );

  const showConverted = fxRate != null && defaultCurrency && currency !== defaultCurrency;
  const displayCurrency = showConverted ? defaultCurrency : currency;
  const toDisplay = (nativePrice) => (showConverted ? nativePrice * fxRate : nativePrice);

  const points = useMemo(
    () => [
      ...historyRecords.map((r) => ({ ...r, isForecast: false })),
      ...forecastRecords.map((r) => ({ ...r, isForecast: true })),
    ],
    [historyRecords, forecastRecords]
  );
  const hasData = points.length > 0;

  const maxAmount = useMemo(
    () => (hasData ? Math.max(...points.map((p) => toDisplay(p.price))) : 1),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [points, showConverted, fxRate]
  );
  const spanDays =
    points.length > 1
      ? (new Date(points[points.length - 1].ex_dividend_date) - new Date(points[0].ex_dividend_date)) /
        (1000 * 60 * 60 * 24)
      : 0;

  const plotWidth = width - PADDING_LEFT - PADDING_RIGHT;
  const plotHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const step = points.length > 0 ? plotWidth / points.length : plotWidth;
  const bottomY = PADDING_TOP + plotHeight;

  const xFor = (i) => PADDING_LEFT + step * (i + 0.5);
  const yFor = (value) => PADDING_TOP + plotHeight * (1 - value / (maxAmount || 1));

  // The forecast line starts from the last historical point (when there is
  // one) so it reads as a continuation of the same series rather than a
  // disconnected second line — same idea as HoldingPriceChart's own
  // comparison overlay always being date-aligned with the main series.
  const historyEndIndex = historyRecords.length - 1;
  const historyPath = historyRecords
    .map((r, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(toDisplay(r.price))}`)
    .join(" ");
  const areaPath =
    historyRecords.length > 0
      ? `${historyPath} L${xFor(historyEndIndex)},${bottomY} L${xFor(0)},${bottomY} Z`
      : "";
  const forecastPath = forecastRecords
    .map((r, i) => {
      const index = historyEndIndex >= 0 ? historyEndIndex + 1 + i : i;
      return `${i === 0 ? "M" : "L"}${xFor(index)},${yFor(toDisplay(r.price))}`;
    })
    .join(" ");
  const forecastLeadIn =
    forecastRecords.length > 0 && historyEndIndex >= 0
      ? `M${xFor(historyEndIndex)},${yFor(toDisplay(historyRecords[historyEndIndex].price))} `
      : "";
  // Closes the same forecastLeadIn+forecastPath line into a filled area,
  // same shape `areaPath` closes historyPath into — down to the axis at
  // the last forecast point, back along the axis to wherever the forecast
  // segment started (the last historical point when there is one, else
  // the first forecast point itself), and up to close the loop.
  const forecastAreaStartIndex = historyEndIndex >= 0 ? historyEndIndex : 0;
  const forecastAreaPath =
    forecastRecords.length > 0
      ? `${forecastLeadIn}${forecastPath} L${xFor(points.length - 1)},${bottomY} L${xFor(
          forecastAreaStartIndex
        )},${bottomY} Z`
      : "";

  const handleMove = (event) => {
    if (!svgRef.current || points.length === 0) return;
    const svg = svgRef.current;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const { x } = point.matrixTransform(svg.getScreenCTM().inverse());
    const index = Math.min(points.length - 1, Math.max(0, Math.floor((x - PADDING_LEFT) / step)));
    setHoverIndex(index);
  };

  const last = points[points.length - 1] ?? null;
  const hovered = hoverIndex !== null ? points[hoverIndex] : last;

  const yTicks = Array.from({ length: Y_AXIS_TICKS + 1 }, (_, i) => {
    const value = (maxAmount * i) / Y_AXIS_TICKS;
    return { key: i, value, y: yFor(value) };
  });
  const xTickIndices = axisTickIndices(points.length, X_AXIS_MAX_TICKS);

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
  }, [revision, historyPath]);

  useLayoutEffect(() => {
    const el = forecastClipRectRef.current;
    if (!el) return;
    el.style.transitionProperty = "none";
    el.setAttribute("width", "0");
    el.getBoundingClientRect();
    el.style.transitionProperty = "";
    el.setAttribute("width", String(Math.max(plotWidth, 0)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revision, forecastPath]);

  if (!hasData) {
    return <p className="ec-chart-caption">No dividend history to show for this range.</p>;
  }

  return (
    <div className="ec-pchart-chart">
      <div className="ec-pchart-toolbar">
        <div className="ec-chart-toggle" role="group" aria-label="Chart type">
          {["line", "area"].map((type) => (
            <button
              key={type}
              type="button"
              className={`ec-chart-toggle-btn${chartType === type ? " is-active" : ""}`}
              onClick={() => bump(setChartType)(type)}
            >
              {type === "line" ? "Line" : "Area"}
            </button>
          ))}
        </div>

        <label className="ec-pchart-events-toggle">
          <input
            type="checkbox"
            checked={showForecast}
            onChange={(event) => bump(setShowForecast)(event.target.checked)}
          />
          <span className="ec-pchart-events-toggle-track" aria-hidden="true" />
          Show forecast
        </label>
      </div>

      <div className="ec-pchart-ranges" role="group" aria-label="Dividend history range">
        {pastRanges.map((range) => (
          <button
            key={range.id}
            type="button"
            className={`ec-pchart-range-btn${range.id === effectivePastRangeId ? " is-active" : ""}`}
            onClick={() => bump(setPastRangeId)(range.id)}
          >
            {range.label}
          </button>
        ))}
        {showForecast && (
          <>
            <span className="ec-pchart-range-sep" aria-hidden="true" />
            {forecastRanges.map((range) => (
              <button
                key={range.id}
                type="button"
                className={`ec-pchart-range-btn${
                  range.id === effectiveForecastRangeId ? " is-active" : ""
                }`}
                onClick={() => bump(setForecastRangeId)(range.id)}
              >
                +{range.label}
              </button>
            ))}
          </>
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
          aria-label="Line chart of dividend payouts, with an optional forecast overlay"
        >
          {yTicks.map(({ key, value, y }) => (
            <g key={key}>
              <line x1={PADDING_LEFT} x2={width - PADDING_RIGHT} y1={y} y2={y} className="ec-chart-gridline" />
              <text x={PADDING_LEFT - 8} y={y} className="ec-chart-axis-label ec-chart-yaxis-label ec-balance">
                {formatPrice(value, displayCurrency)}
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
              {formatAxisDate(points[i].ex_dividend_date, spanDays)}
            </text>
          ))}

          {chartType === "area" && historyRecords.length > 0 && (
            <g className="ec-chart-reveal" key={revision}>
              <path d={areaPath} className="ec-pchart-area" />
            </g>
          )}
          {historyRecords.length > 0 && (
            <path ref={mainLineRef} d={historyPath} className="ec-chart-line" fill="none" />
          )}

          {forecastRecords.length > 0 && (
            <>
              <defs>
                <clipPath id={forecastClipId}>
                  <rect
                    ref={forecastClipRectRef}
                    x={PADDING_LEFT}
                    y={PADDING_TOP}
                    width={plotWidth}
                    height={plotHeight}
                  />
                </clipPath>
              </defs>
              {chartType === "area" && (
                <g className="ec-chart-reveal" key={revision}>
                  <path d={forecastAreaPath} className="ec-pchart-forecast-area" />
                </g>
              )}
              <path
                d={`${forecastLeadIn}${forecastPath}`}
                className="ec-pchart-compare-line"
                fill="none"
                clipPath={`url(#${forecastClipId})`}
              />
            </>
          )}

          {hoverIndex !== null && (
            <line x1={xFor(hoverIndex)} x2={xFor(hoverIndex)} y1={PADDING_TOP} y2={bottomY} className="ec-chart-crosshair" />
          )}
        </svg>
      </div>

      {hovered && (
        <div className="ec-chart-tooltip">
          <span className="ec-chart-tooltip-date">
            {new Date(hovered.ex_dividend_date).toLocaleDateString(undefined, {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
          </span>
          <Balance>{formatPrice(toDisplay(hovered.price), displayCurrency)}</Balance>
          {showConverted && (
            <span className="ec-dividend-native-amount">({formatPrice(hovered.price, currency)})</span>
          )}
          <span>{STATUS_LABEL[hovered.status]}</span>
        </div>
      )}
    </div>
  );
}

export default HoldingDividendChart;
