import { useMemo, useRef, useState } from "react";
import Balance from "../../components/core/Balance.jsx";
import { formatPrice } from "./holdingFinancials.js";
import "../accounts/PriceChart.css";
import "./HoldingPriceChart.css";

const WIDTH = 720;
const HEIGHT = 220;
const PADDING_TOP = 16;
const PADDING_RIGHT = 12;
const PADDING_BOTTOM = 28;
const PADDING_LEFT = 56;
const Y_AXIS_TICKS = 4;
const X_AXIS_MAX_TICKS = 6;

/** A bar's date span past which the x-axis switches to a coarser "Mon YY"
 * label instead of "Mon D" — same rough 2-year-ish threshold
 * HoldingPriceChart's LONG_RANGES draws its own line at, just computed
 * from the records' actual span instead of a caller-picked range id, so
 * this reacts correctly whether `records` came from an explicit range
 * (the Past tab) or whatever span the data itself happens to have (the
 * Upcoming tab, bounded only by the forecast horizon). */
const COARSE_AXIS_SPAN_DAYS = 500;

function isCoarseSpan(records) {
  if (records.length < 2) return false;
  const first = new Date(records[0].ex_dividend_date);
  const last = new Date(records[records.length - 1].ex_dividend_date);
  return (last - first) / (1000 * 60 * 60 * 24) > COARSE_AXIS_SPAN_DAYS;
}

function formatAxisDate(dateStr, coarse) {
  const date = new Date(dateStr);
  if (coarse) return date.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Evenly spaced bar indices to label on the x-axis — at most `maxTicks`,
 * always including the first and last bar. Duplicated from
 * HoldingPriceChart.jsx's own copy rather than shared - a tiny, self-
 * contained helper, not worth a new shared module for two call sites. */
function axisTickIndices(count, maxTicks) {
  if (count <= 1) return [0].slice(0, count);
  const tickCount = Math.min(maxTicks, count);
  const indices = new Set();
  for (let i = 0; i < tickCount; i += 1) {
    indices.add(Math.round((i * (count - 1)) / (tickCount - 1)));
  }
  return [...indices].sort((a, b) => a - b);
}

const STATUS_BAR_CLASS = { paid: "", declared: "is-declared", estimated: "is-estimated" };
const STATUS_LABEL = { paid: "Paid", declared: "Declared", estimated: "Estimated" };

/**
 * A generic SVG bar chart of dividend records — one bar per record,
 * ascending by ex-dividend date — shared by the "See all" drawer's Past
 * (real historical payouts) and Upcoming (declared/estimated) tabs.
 * `colorByStatus` colors each bar to match its Declared/Estimated badge
 * tone (green/blue) for the Upcoming tab's mixed list; the Past tab's
 * records are all `"paid"`, so it leaves this off and every bar renders in
 * the chart's plain accent color instead. `emptyMessage` renders in place
 * of the chart when `records` is empty (e.g. nothing in the selected
 * history range, or no upcoming dividends at all).
 *
 * @param {{ records: import("../../api/market.js").DividendRecord[], currency: string|null, colorByStatus?: boolean, emptyMessage: string }} props
 */
function HoldingDividendBarChart({ records, currency, colorByStatus = false, emptyMessage }) {
  const [hoverIndex, setHoverIndex] = useState(null);
  const svgRef = useRef(null);

  const maxAmount = useMemo(
    () => (records.length > 0 ? Math.max(...records.map((record) => record.price)) : 1),
    [records]
  );
  const coarseAxis = useMemo(() => isCoarseSpan(records), [records]);

  if (records.length === 0) {
    return <p className="ec-chart-caption">{emptyMessage}</p>;
  }

  const plotWidth = WIDTH - PADDING_LEFT - PADDING_RIGHT;
  const plotHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const step = plotWidth / records.length;
  const bottomY = PADDING_TOP + plotHeight;

  const xFor = (i) => PADDING_LEFT + step * (i + 0.5);
  const yFor = (value) => PADDING_TOP + plotHeight * (1 - value / maxAmount);
  const barHeight = (value) => bottomY - yFor(value);

  const handleMove = (event) => {
    if (!svgRef.current) return;
    const svg = svgRef.current;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const { x } = point.matrixTransform(svg.getScreenCTM().inverse());
    const index = Math.min(records.length - 1, Math.max(0, Math.floor((x - PADDING_LEFT) / step)));
    setHoverIndex(index);
  };

  const yTicks = Array.from({ length: Y_AXIS_TICKS + 1 }, (_, i) => {
    const value = (maxAmount * i) / Y_AXIS_TICKS;
    return { key: i, value, y: yFor(value) };
  });
  const xTickIndices = axisTickIndices(records.length, X_AXIS_MAX_TICKS);
  const hovered = hoverIndex !== null ? records[hoverIndex] : null;

  return (
    <>
      <svg
        ref={svgRef}
        className="ec-chart-svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIndex(null)}
        role="img"
        aria-label="Bar chart of dividend payouts"
      >
        {yTicks.map(({ key, value, y }) => (
          <g key={key}>
            <line x1={PADDING_LEFT} x2={WIDTH - PADDING_RIGHT} y1={y} y2={y} className="ec-chart-gridline" />
            <text x={PADDING_LEFT - 8} y={y} className="ec-chart-axis-label ec-chart-yaxis-label ec-balance">
              {formatPrice(value, currency)}
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
            {formatAxisDate(records[i].ex_dividend_date, coarseAxis)}
          </text>
        ))}

        {records.map((record, i) => (
          <rect
            key={`${record.status}-${record.ex_dividend_date}`}
            x={xFor(i) - step * 0.3}
            y={yFor(record.price)}
            width={step * 0.6}
            height={Math.max(1.5, barHeight(record.price))}
            className={`ec-dividend-bar${colorByStatus ? ` ${STATUS_BAR_CLASS[record.status]}` : ""}${
              i === hoverIndex ? " is-hovered" : ""
            }`}
          />
        ))}

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
          <span className="ec-chart-tooltip-date">
            {new Date(hovered.ex_dividend_date).toLocaleDateString(undefined, {
              day: "numeric",
              month: "short",
              year: "numeric",
            })}
          </span>
          <Balance>{formatPrice(hovered.price, currency)}</Balance>
          {colorByStatus && <span>{STATUS_LABEL[hovered.status]}</span>}
        </div>
      )}
    </>
  );
}

export default HoldingDividendBarChart;
