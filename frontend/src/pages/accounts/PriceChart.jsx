import { useMemo, useRef, useState } from "react";
import Card from "../../components/core/Card.jsx";
import { seededRandom } from "../../utils/deterministicRandom.js";
import "./PriceChart.css";

/**
 * Standard index benchmarks offered in the "Compare against" picker,
 * alongside the other portfolios passed in via `pies` (an account's own
 * pies, or a pie's sibling pies in the same account — see AccountDetailPage/
 * PieDetailPage). Purely illustrative (see module docstring below): no
 * real benchmark data is fetched.
 */
const BENCHMARKS = [
  { id: "sp500", name: "S&P 500" },
  { id: "nasdaq100", name: "NASDAQ 100" },
  { id: "ftse100", name: "FTSE 100" },
];

/**
 * Every selectable range, with how many synthetic bars it renders and how
 * far apart (in days) each bar sits — a fixed lookup rather than real
 * calendar-aware trading-day math, since the whole series is fake anyway.
 * "ytd" is the one exception: its bar count depends on today's date, so
 * it's computed in `rangeBarCount` instead of listed here.
 */
const RANGES = [
  { id: "1d", label: "1D", count: 8, stepDays: 0, intraday: true },
  { id: "5d", label: "5D", count: 5, stepDays: 1 },
  { id: "1m", label: "1M", count: 22, stepDays: 1 },
  { id: "6m", label: "6M", count: 26, stepDays: 7 },
  { id: "ytd", label: "YTD", count: null, stepDays: 7 },
  { id: "1y", label: "1Y", count: 52, stepDays: 7 },
  { id: "2y", label: "2Y", count: 24, stepDays: 30 },
  { id: "3y", label: "3Y", count: 36, stepDays: 30 },
  { id: "5y", label: "5Y", count: 60, stepDays: 30 },
  { id: "10y", label: "10Y", count: 60, stepDays: 60 },
  { id: "max", label: "MAX", count: 60, stepDays: 90 },
];

function ytdBarCount() {
  const now = new Date();
  const startOfYear = new Date(now.getFullYear(), 0, 1);
  const days = Math.floor((now - startOfYear) / 86400000);
  return Math.max(2, Math.round(days / 7));
}

function rangeBarCount(range) {
  return range.id === "ytd" ? ytdBarCount() : range.count;
}

/** A synthetic close-price random walk, indexed to 100 at the first bar. */
function buildCloses(count, seedLabel) {
  const rand = seededRandom(seedLabel);
  const closes = [100];
  for (let i = 1; i < count; i += 1) {
    const changePct = (rand() - 0.48) * 3;
    closes.push(Math.max(20, closes[i - 1] * (1 + changePct / 100)));
  }
  return closes;
}

function buildBars(closes) {
  return closes.map((close, i) => {
    const open = i === 0 ? close - 0.4 : closes[i - 1];
    const wiggle = 0.5 + (i % 3) * 0.15;
    return {
      open,
      close,
      high: Math.max(open, close) + wiggle,
      low: Math.min(open, close) - wiggle,
    };
  });
}

function trailingLabels(count, { stepDays, intraday }) {
  const labels = [];
  const now = new Date();
  for (let i = count - 1; i >= 0; i -= 1) {
    const d = new Date(now);
    if (intraday) {
      d.setHours(d.getHours() - i);
      labels.push(d.toLocaleTimeString(undefined, { hour: "numeric" }));
    } else {
      d.setDate(d.getDate() - i * stepDays);
      labels.push(
        stepDays >= 28
          ? d.toLocaleDateString(undefined, { month: "short", year: "2-digit" })
          : d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
      );
    }
  }
  return labels;
}

const WIDTH = 720;
const HEIGHT = 260;
const PADDING = 24;

/**
 * A hand-rolled SVG chart consolidating every holding under `seedKey`'s
 * subject (an account's pies + direct holdings, or one pie's own holdings)
 * into one illustrative price trend — same "no API hits, synthetic data"
 * approach as SignInScreen's DemoChart, extended with an Area chart type,
 * the full 1D..MAX range set, and an optional "compare against" overlay
 * (another portfolio, another of the user's holdings, or a standard index
 * benchmark) — the overlay series is equally synthetic; wiring up real
 * comparisons is a later phase.
 *
 * `seedKey` must be unique per subject (e.g. `account:<id>` / `pie:<id>` /
 * `holding:<ticker>`) so different accounts/pies/holdings don't render the
 * exact same illustrative shape. `subjectLabel` names that subject in the
 * legend/caption/aria-label ("This account" vs "This portfolio" vs "This
 * holding"). `holdings` (id/name pairs) is the HoldingTickerPage
 * equivalent of `pies` — only one of the two is normally passed by any
 * given caller, but both default to `[]` so either can be omitted.
 */
function PriceChart({ pies = [], holdings = [], seedKey, subjectLabel = "This account" }) {
  const [chartType, setChartType] = useState("line");
  const [rangeId, setRangeId] = useState("1y");
  const [compareId, setCompareId] = useState("");
  const [hoverIndex, setHoverIndex] = useState(null);
  const svgRef = useRef(null);

  const range = RANGES.find((r) => r.id === rangeId) ?? RANGES[0];
  const count = rangeBarCount(range);

  const closes = useMemo(() => buildCloses(count, `${seedKey}:${rangeId}`), [count, seedKey, rangeId]);
  const bars = useMemo(() => buildBars(closes), [closes]);
  const labels = useMemo(() => trailingLabels(count, range), [count, range]);

  const compareLabel = useMemo(() => {
    if (!compareId) return null;
    if (compareId.startsWith("pie:")) {
      return pies.find((p) => `pie:${p.id}` === compareId)?.name ?? null;
    }
    if (compareId.startsWith("holding:")) {
      return holdings.find((h) => `holding:${h.id}` === compareId)?.name ?? null;
    }
    return BENCHMARKS.find((b) => `benchmark:${b.id}` === compareId)?.name ?? null;
  }, [compareId, pies, holdings]);

  const compareCloses = useMemo(
    () => (compareId ? buildCloses(count, `${compareId}:${rangeId}`) : null),
    [compareId, count, rangeId]
  );

  const { min, max } = useMemo(() => {
    const values = bars.flatMap((b) => [b.high, b.low]);
    if (compareCloses) values.push(...compareCloses);
    return { min: Math.min(...values), max: Math.max(...values) };
  }, [bars, compareCloses]);

  const rangeSpan = max - min || 1;
  const plotWidth = WIDTH - PADDING * 2;
  const plotHeight = HEIGHT - PADDING * 2;
  const step = plotWidth / bars.length;

  const xFor = (i) => PADDING + step * (i + 0.5);
  const yFor = (value) => PADDING + plotHeight * (1 - (value - min) / rangeSpan);
  const bottomY = PADDING + plotHeight;

  const linePath = bars.map((b, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(b.close)}`).join(" ");
  const areaPath = `${linePath} L${xFor(bars.length - 1)},${bottomY} L${xFor(0)},${bottomY} Z`;
  const comparePath = compareCloses
    ? compareCloses.map((v, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(v)}`).join(" ")
    : null;

  const first = bars[0];
  const last = bars[bars.length - 1];
  const changePct = ((last.close - first.open) / first.open) * 100;
  const isUp = changePct >= 0;

  const compareChangePct = compareCloses
    ? ((compareCloses[compareCloses.length - 1] - compareCloses[0]) / compareCloses[0]) * 100
    : null;

  const handleMove = (event) => {
    if (!svgRef.current) return;
    const svg = svgRef.current;
    // getBoundingClientRect()'s width is a plain pixel-ratio scale, which
    // assumes the viewBox fills that box exactly — the rendered box's
    // aspect ratio rarely matches WIDTH:HEIGHT, so the default
    // preserveAspectRatio ("xMidYMid meet") letterboxes it, throwing that
    // mapping off from where the cursor actually is. getScreenCTM() is the
    // real screen-pixel-to-viewBox transform, correct regardless of any
    // letterboxing.
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const { x } = point.matrixTransform(svg.getScreenCTM().inverse());
    const index = Math.min(bars.length - 1, Math.max(0, Math.floor((x - PADDING) / step)));
    setHoverIndex(index);
  };

  const hovered = hoverIndex !== null ? bars[hoverIndex] : last;
  const hoveredLabel = hoverIndex !== null ? labels[hoverIndex] : labels[labels.length - 1];

  return (
    <Card className="ec-pchart">
      <div className="ec-pchart-toolbar">
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

        <select
          className="ec-pchart-compare"
          value={compareId}
          onChange={(event) => setCompareId(event.target.value)}
          aria-label="Compare against"
        >
          <option value="">Compare against…</option>
          {pies.length > 0 && (
            <optgroup label="Portfolios in this account">
              {pies.map((pie) => (
                <option key={pie.id} value={`pie:${pie.id}`}>
                  {pie.name}
                </option>
              ))}
            </optgroup>
          )}
          {holdings.length > 0 && (
            <optgroup label="Other holdings">
              {holdings.map((holding) => (
                <option key={holding.id} value={`holding:${holding.id}`}>
                  {holding.name}
                </option>
              ))}
            </optgroup>
          )}
          <optgroup label="Benchmarks">
            {BENCHMARKS.map((benchmark) => (
              <option key={benchmark.id} value={`benchmark:${benchmark.id}`}>
                {benchmark.name}
              </option>
            ))}
          </optgroup>
        </select>
      </div>

      <div className="ec-pchart-ranges" role="group" aria-label="Date range">
        {RANGES.map((r) => (
          <button
            key={r.id}
            type="button"
            className={`ec-pchart-range-btn${r.id === rangeId ? " is-active" : ""}`}
            onClick={() => {
              setRangeId(r.id);
              setHoverIndex(null);
            }}
          >
            {r.label}
          </button>
        ))}
      </div>

      <div className="ec-pchart-legend">
        <span className="ec-pchart-legend-item">
          <span className="ec-pchart-dot ec-pchart-dot--main" aria-hidden="true" />
          {subjectLabel}
          <span className={`ec-chart-change${isUp ? " is-up" : " is-down"}`}>
            {isUp ? "▲" : "▼"} {Math.abs(changePct).toFixed(1)}%
          </span>
        </span>
        {compareLabel && compareChangePct !== null && (
          <span className="ec-pchart-legend-item">
            <span className="ec-pchart-dot ec-pchart-dot--compare" aria-hidden="true" />
            {compareLabel}
            <span className={`ec-chart-change${compareChangePct >= 0 ? " is-up" : " is-down"}`}>
              {compareChangePct >= 0 ? "▲" : "▼"} {Math.abs(compareChangePct).toFixed(1)}%
            </span>
          </span>
        )}
      </div>

      <svg
        ref={svgRef}
        className="ec-chart-svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIndex(null)}
        role="img"
        aria-label={`Illustrative consolidated ${chartType} chart for ${subjectLabel.toLowerCase()}'s holdings`}
      >
        {[0.25, 0.5, 0.75].map((frac) => (
          <line
            key={frac}
            x1={PADDING}
            x2={WIDTH - PADDING}
            y1={PADDING + plotHeight * frac}
            y2={PADDING + plotHeight * frac}
            className="ec-chart-gridline"
          />
        ))}

        {chartType === "area" && <path d={areaPath} className="ec-pchart-area" />}
        {(chartType === "line" || chartType === "area") && (
          <path d={linePath} className="ec-chart-line" fill="none" />
        )}
        {chartType === "candle" &&
          bars.map((b, i) => (
            <g key={labels[i]}>
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

        {comparePath && <path d={comparePath} className="ec-pchart-compare-line" fill="none" />}

        {hoverIndex !== null && (
          <line
            x1={xFor(hoverIndex)}
            x2={xFor(hoverIndex)}
            y1={PADDING}
            y2={HEIGHT - PADDING}
            className="ec-chart-crosshair"
          />
        )}
      </svg>

      <div className="ec-chart-tooltip">
        <span className="ec-chart-tooltip-date">{hoveredLabel}</span>
        <span>O {hovered.open.toFixed(1)}</span>
        <span>H {hovered.high.toFixed(1)}</span>
        <span>L {hovered.low.toFixed(1)}</span>
        <span>C {hovered.close.toFixed(1)}</span>
      </div>

      <p className="ec-chart-caption">
        Illustrative sample data, indexed to 100 at the start of the period — consolidates every
        holding under {subjectLabel.toLowerCase()} into one trend, not real prices. Comparison
        series are equally synthetic; real portfolio/benchmark comparisons are a later phase.
      </p>
    </Card>
  );
}

export default PriceChart;
