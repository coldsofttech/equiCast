import { useMemo, useRef, useState } from "react";
import "./DemoChart.css";

/**
 * Fully synthetic, hand-authored close-price series — indexed to 100 at the
 * start of the period rather than real dollar prices, precisely so this
 * can't be mistaken for actual quotes. Static (not fetched), which is the
 * point: this demonstrates the *shape* of the chart the product renders,
 * not a live data feed.
 */
const TICKERS = [
  {
    symbol: "AAPL",
    name: "Apple",
    closes: [
      100, 100.8, 101.4, 100.9, 102.1, 103.0, 102.4, 103.8, 104.5, 103.9, 105.2, 106.0, 105.4, 107.1,
      108.0, 107.6,
    ],
  },
  {
    symbol: "NVDA",
    name: "NVIDIA",
    closes: [
      100, 103.5, 101.2, 106.8, 104.0, 110.5, 107.2, 115.0, 111.8, 118.4, 114.9, 121.6, 117.3, 124.8,
      120.1, 128.4,
    ],
  },
  {
    symbol: "AMZN",
    name: "Amazon",
    closes: [
      100, 99.2, 100.6, 98.8, 101.3, 100.1, 102.4, 101.0, 99.6, 100.9, 102.8, 101.5, 103.2, 102.0,
      104.1, 103.3,
    ],
  },
];

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

function trailingDayLabels(count) {
  const labels = [];
  const today = new Date();
  for (let i = count - 1; i >= 0; i -= 1) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    labels.push(d.toLocaleDateString(undefined, { month: "short", day: "numeric" }));
  }
  return labels;
}

const WIDTH = 640;
const HEIGHT = 220;
const PADDING = 24;

/**
 * A hand-rolled SVG candle/line chart for the landing page — ticker tabs,
 * a chart-type toggle, and a hover crosshair reading out OHLC for the
 * nearest bar. No charting library; the data is synthetic (see TICKERS).
 */
function DemoChart() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [chartType, setChartType] = useState("candle");
  const [hoverIndex, setHoverIndex] = useState(null);
  const svgRef = useRef(null);

  const ticker = TICKERS[activeIndex];
  const bars = useMemo(() => buildBars(ticker.closes), [ticker]);
  const labels = useMemo(() => trailingDayLabels(bars.length), [bars.length]);

  const { min, max } = useMemo(() => {
    const values = bars.flatMap((b) => [b.high, b.low]);
    return { min: Math.min(...values), max: Math.max(...values) };
  }, [bars]);

  const range = max - min || 1;
  const plotWidth = WIDTH - PADDING * 2;
  const plotHeight = HEIGHT - PADDING * 2;
  const step = plotWidth / bars.length;

  const xFor = (i) => PADDING + step * (i + 0.5);
  const yFor = (value) => PADDING + plotHeight * (1 - (value - min) / range);

  const linePath = bars.map((b, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(b.close)}`).join(" ");

  const first = bars[0];
  const last = bars[bars.length - 1];
  const changePct = ((last.close - first.open) / first.open) * 100;
  const isUp = changePct >= 0;

  const handleMove = (event) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const index = Math.min(bars.length - 1, Math.max(0, Math.floor((x - PADDING) / step)));
    setHoverIndex(index);
  };

  const hovered = hoverIndex !== null ? bars[hoverIndex] : last;
  const hoveredLabel = hoverIndex !== null ? labels[hoverIndex] : labels[labels.length - 1];

  return (
    <section className="ec-demo">
      <span className="ec-section-eyebrow">See it in action</span>
      <h2 className="ec-features-title">What tracking a ticker could look like</h2>
      <p className="ec-demo-sub">
        Illustrative sample data, indexed to 100 at the start of the period — not real prices. As of{" "}
        {new Date().toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}.
      </p>

      <div className="ec-demo-card">
        <div className="ec-demo-toolbar">
          <div className="ec-demo-tabs" role="tablist" aria-label="Ticker">
            {TICKERS.map((t, i) => (
              <button
                key={t.symbol}
                type="button"
                role="tab"
                aria-selected={i === activeIndex}
                className={`ec-demo-tab${i === activeIndex ? " is-active" : ""}`}
                onClick={() => {
                  setActiveIndex(i);
                  setHoverIndex(null);
                }}
              >
                {t.symbol}
              </button>
            ))}
          </div>
          <div className="ec-chart-toggle" role="group" aria-label="Chart type">
            <button
              type="button"
              className={`ec-chart-toggle-btn${chartType === "candle" ? " is-active" : ""}`}
              onClick={() => setChartType("candle")}
            >
              Candles
            </button>
            <button
              type="button"
              className={`ec-chart-toggle-btn${chartType === "line" ? " is-active" : ""}`}
              onClick={() => setChartType("line")}
            >
              Line
            </button>
          </div>
        </div>

        <div className="ec-demo-stats">
          <span className="ec-demo-name">
            {ticker.name} <span className="ec-demo-symbol">{ticker.symbol}</span>
          </span>
          <span className={`ec-chart-change${isUp ? " is-up" : " is-down"}`}>
            {isUp ? "▲" : "▼"} {Math.abs(changePct).toFixed(1)}%
          </span>
        </div>

        <svg
          ref={svgRef}
          className="ec-chart-svg"
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          onMouseMove={handleMove}
          onMouseLeave={() => setHoverIndex(null)}
          role="img"
          aria-label={`Illustrative ${chartType === "candle" ? "candlestick" : "line"} chart for ${ticker.name}`}
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

          {chartType === "line" ? (
            <path d={linePath} className="ec-chart-line" fill="none" />
          ) : (
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
            ))
          )}

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
      </div>
    </section>
  );
}

export default DemoChart;
