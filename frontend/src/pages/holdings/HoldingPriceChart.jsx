import { useEffect, useMemo, useRef, useState } from "react";
import Card from "../../components/core/Card.jsx";
import { useApi } from "../../api/useApi.js";
import { getPrices } from "../../api/market.js";
import { seededRandom } from "../../utils/deterministicRandom.js";
import { formatPrice } from "./holdingFinancials.js";
import "../accounts/PriceChart.css";
import "./HoldingPriceChart.css";

/** Same benchmark list PriceChart.jsx offers — duplicated rather than
 * imported/exported since it's a tiny, purely-illustrative constant (real
 * benchmark data is a later phase, same disclaimer as the account/pie
 * chart's compare overlay). */
const BENCHMARKS = [
  { id: "sp500", name: "S&P 500" },
  { id: "nasdaq100", name: "NASDAQ 100" },
  { id: "ftse100", name: "FTSE 100" },
];

/** Every range this picker offers (see market.js's PRICE_RANGES for the
 * full set the backend accepts) — "1d" is deliberately omitted: only
 * daily bars are ever stored, so a "1 day" range would just be the single
 * latest row, not a meaningful chart. */
const RANGES = [
  { id: "5d", label: "5D" },
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

/** A synthetic close-price random walk, indexed to 100 at the first bar —
 * only ever used for the "compare against" overlay (other holdings/
 * benchmarks), never for this chart's own subject series, which is real.
 * Sized to match the real series' own bar count so both lines plot against
 * the same x-axis. */
function buildCompareCloses(count, seedLabel) {
  const rand = seededRandom(seedLabel);
  const closes = [100];
  for (let i = 1; i < count; i += 1) {
    const changePct = (rand() - 0.48) * 3;
    closes.push(Math.max(20, closes[i - 1] * (1 + changePct / 100)));
  }
  return closes;
}

function formatAxisDate(dateStr, rangeId) {
  const d = new Date(dateStr);
  if (VERY_LONG_RANGES.has(rangeId)) return d.toLocaleDateString(undefined, { year: "numeric" });
  if (LONG_RANGES.has(rangeId)) return d.toLocaleDateString(undefined, { month: "short", year: "2-digit" });
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
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

const WIDTH = 720;
const HEIGHT = 260;
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
 * walk. The compare overlay (other holdings/benchmarks) stays synthetic —
 * real multi-series comparison is a later phase — so it's built the same
 * way PriceChart.jsx's is, just resized to this chart's real bar count.
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
 * ticker was originally bought).
 *
 * @param {{ assetClass: string, ticker: string, currency: string|null, holdings?: {id: string, name: string}[], avgPrice?: number|null }} props
 */
function HoldingPriceChart({ assetClass, ticker, currency, holdings = [], avgPrice = null }) {
  const api = useApi();
  const [chartType, setChartType] = useState("line");
  const [rangeId, setRangeId] = useState("max");
  const [compareId, setCompareId] = useState("");
  const [hoverIndex, setHoverIndex] = useState(null);
  const svgRef = useRef(null);

  const [series, setSeries] = useState(null);
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setHoverIndex(null);
    getPrices(api, assetClass, ticker, { range: rangeId })
      .then((result) => {
        if (cancelled) return;
        setSeries(result);
        setStatus(result.prices.length > 0 ? "ok" : "empty");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [api, assetClass, ticker, rangeId]);

  const bars = useMemo(() => series?.prices ?? [], [series]);
  const seriesCurrency = series?.currency ?? currency ?? null;

  const compareLabel = useMemo(() => {
    if (!compareId) return null;
    if (compareId.startsWith("holding:")) {
      return holdings.find((h) => `holding:${h.id}` === compareId)?.name ?? null;
    }
    return BENCHMARKS.find((b) => `benchmark:${b.id}` === compareId)?.name ?? null;
  }, [compareId, holdings]);

  const compareCloses = useMemo(
    () => (compareId && bars.length > 0 ? buildCompareCloses(bars.length, `${compareId}:${ticker}:${rangeId}`) : null),
    [compareId, bars.length, ticker, rangeId]
  );

  const { min, max } = useMemo(() => {
    if (bars.length === 0) return { min: 0, max: 1 };
    const values = bars.flatMap((b) => [b.high, b.low]);
    if (compareCloses) values.push(...compareCloses);
    if (avgPrice != null) values.push(avgPrice);
    return { min: Math.min(...values), max: Math.max(...values) };
  }, [bars, compareCloses, avgPrice]);

  const rangeSpan = max - min || 1;
  const plotWidth = WIDTH - PADDING_LEFT - PADDING_RIGHT;
  const plotHeight = HEIGHT - PADDING_TOP - PADDING_BOTTOM;
  const step = bars.length > 0 ? plotWidth / bars.length : plotWidth;

  const xFor = (i) => PADDING_LEFT + step * (i + 0.5);
  const yFor = (value) => PADDING_TOP + plotHeight * (1 - (value - min) / rangeSpan);
  const bottomY = PADDING_TOP + plotHeight;

  const linePath = bars.map((b, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(b.close)}`).join(" ");
  const areaPath = bars.length > 0 ? `${linePath} L${xFor(bars.length - 1)},${bottomY} L${xFor(0)},${bottomY} Z` : "";
  const comparePath = compareCloses
    ? compareCloses.map((v, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(v)}`).join(" ")
    : null;

  const first = bars[0];
  const last = bars[bars.length - 1];
  const changePct = first && last ? ((last.close - first.open) / first.open) * 100 : null;
  const isUp = (changePct ?? 0) >= 0;

  const compareChangePct = compareCloses
    ? ((compareCloses[compareCloses.length - 1] - compareCloses[0]) / compareCloses[0]) * 100
    : null;

  const handleMove = (event) => {
    if (!svgRef.current || bars.length === 0) return;
    const svg = svgRef.current;
    // Mapping clientX through getBoundingClientRect()'s width (a plain
    // pixel-ratio scale) assumes the viewBox fills that box exactly — the
    // rendered box's aspect ratio rarely matches WIDTH:HEIGHT exactly, so
    // the default preserveAspectRatio ("xMidYMid meet") letterboxes it,
    // which throws that mapping off from where the cursor actually is.
    // getScreenCTM() is the real screen-pixel-to-viewBox transform, so
    // it's correct regardless of any letterboxing.
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
            onClick={() => setRangeId(r.id)}
          >
            {r.label}
          </button>
        ))}
      </div>

      {status === "loading" && <p className="ec-loading">Loading price history…</p>}
      {status === "error" && <p className="ec-chart-caption">Couldn&rsquo;t load price history for {ticker}.</p>}
      {status === "empty" && (
        <p className="ec-chart-caption">No price history published for {ticker} for this range yet.</p>
      )}

      {status === "ok" && (
        <>
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
            {compareLabel && compareChangePct !== null && (
              <span className="ec-pchart-legend-item">
                <span className="ec-pchart-dot ec-pchart-dot--compare" aria-hidden="true" />
                {compareLabel}
                <span className={`ec-chart-change${compareChangePct >= 0 ? " is-up" : " is-down"}`}>
                  {compareChangePct >= 0 ? "▲" : "▼"} {Math.abs(compareChangePct).toFixed(1)}%
                </span>
              </span>
            )}
            {avgPrice != null && (
              <span className="ec-pchart-legend-item">
                <span className="ec-pchart-swatch" aria-hidden="true" />
                Avg buy price: {formatPrice(avgPrice, seriesCurrency)}
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
            aria-label={`${chartType} chart of ${ticker}'s real price history for the ${rangeId} range`}
          >
            {yTicks.map(({ key, value, y }) => (
              <g key={key}>
                <line
                  x1={PADDING_LEFT}
                  x2={WIDTH - PADDING_RIGHT}
                  y1={y}
                  y2={y}
                  className="ec-chart-gridline"
                />
                <text x={PADDING_LEFT - 8} y={y} className="ec-chart-axis-label ec-chart-yaxis-label">
                  {formatPrice(value, seriesCurrency)}
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

            {chartType === "area" && <path d={areaPath} className="ec-pchart-area" />}
            {(chartType === "line" || chartType === "area") && (
              <path d={linePath} className="ec-chart-line" fill="none" />
            )}
            {chartType === "candle" &&
              bars.map((b, i) => (
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

            {comparePath && <path d={comparePath} className="ec-pchart-compare-line" fill="none" />}

            {avgPrice != null && (
              <line
                x1={PADDING_LEFT}
                x2={WIDTH - PADDING_RIGHT}
                y1={yFor(avgPrice)}
                y2={yFor(avgPrice)}
                className="ec-chart-avg-line"
              />
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

          {compareLabel && (
            <p className="ec-chart-caption">
              {compareLabel}&rsquo;s comparison line is illustrative sample data — real
              multi-series comparison is a later phase.
            </p>
          )}
        </>
      )}
    </Card>
  );
}

export default HoldingPriceChart;
