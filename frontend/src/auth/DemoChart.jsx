import { useEffect, useMemo, useRef, useState } from "react";
import { getPublicDemoPrices } from "../api/publicMarket.js";
import { readCachedDemoPrices, writeCachedDemoPrices } from "../utils/publicDemoPricesCache.js";
import "./DemoChart.css";

const WIDTH = 640;
const HEIGHT = 220;
const PADDING = 24;

function formatBarDate(dateStr) {
  // "YYYY-MM-DD" parsed as local, not UTC-shifted-then-off-by-one — same
  // reasoning as elsewhere in the app that formats a bare date string.
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

/**
 * A hand-rolled SVG candle/line chart for the landing page — ticker tabs,
 * a chart-type toggle, and a hover crosshair reading out OHLC for the
 * nearest bar. No charting library.
 *
 * Real data, not synthetic: fetches `getPublicDemoPrices()` once on mount
 * (the landing page's one unauthenticated market-data call — see that
 * function's own docstring) for a fixed three tickers (AAPL, NVDA, VOO),
 * each ~1 month of real daily OHLC bars. Same daily-refresh cadence as
 * every other price shown once signed in (see the app's own market-data
 * disclaimer) — as current as equicast's data gets, not real-time/intraday.
 * Cached in localStorage for the rest of the
 * calendar day (see publicDemoPricesCache.js), so repeat landing-page
 * visits/reloads before sign-in don't re-hit this rate-limited endpoint.
 */
function DemoChart() {
  const [tickers, setTickers] = useState(null);
  const [error, setError] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [chartType, setChartType] = useState("line");
  const [hoverIndex, setHoverIndex] = useState(null);
  const svgRef = useRef(null);

  useEffect(() => {
    const cached = readCachedDemoPrices();
    if (cached) {
      setTickers(cached.tickers);
      return undefined;
    }

    let cancelled = false;
    getPublicDemoPrices()
      .then((result) => {
        if (cancelled) return;
        setTickers(result.tickers);
        writeCachedDemoPrices(result);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ticker = tickers?.[activeIndex];
  const bars = useMemo(
    () =>
      (ticker?.prices ?? []).filter(
        (b) => b.open != null && b.high != null && b.low != null && b.close != null
      ),
    [ticker]
  );
  const labels = useMemo(() => bars.map((b) => formatBarDate(b.date)), [bars]);

  const { min, max } = useMemo(() => {
    if (!bars.length) return { min: 0, max: 1 };
    const values = bars.flatMap((b) => [b.high, b.low]);
    return { min: Math.min(...values), max: Math.max(...values) };
  }, [bars]);

  const range = max - min || 1;
  const plotWidth = WIDTH - PADDING * 2;
  const plotHeight = HEIGHT - PADDING * 2;
  const step = bars.length ? plotWidth / bars.length : plotWidth;

  const xFor = (i) => PADDING + step * (i + 0.5);
  const yFor = (value) => PADDING + plotHeight * (1 - (value - min) / range);

  const linePath = bars.map((b, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(b.close)}`).join(" ");
  const bottomY = HEIGHT - PADDING;
  const areaPath = bars.length ? `${linePath} L${xFor(bars.length - 1)},${bottomY} L${xFor(0)},${bottomY} Z` : "";

  const first = bars[0];
  const last = bars[bars.length - 1];
  const changePct = first && last ? ((last.close - first.open) / first.open) * 100 : 0;
  const isUp = changePct >= 0;

  const handleMove = (event) => {
    if (!svgRef.current || !bars.length) return;
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
      <h2 className="ec-features-title">Real tickers, tracked the way equiCast tracks them</h2>
      <p className="ec-demo-sub">
        Prices for AAPL, NVDA and VOO — the same figures you'd see once signed in, refreshed daily
        rather than minute-by-minute.
      </p>

      <div className="ec-demo-card">
        {error && <p className="ec-demo-error">Prices are temporarily unavailable.</p>}
        {!error && !tickers && <p className="ec-demo-loading">Loading prices…</p>}

        {!error && tickers && ticker && (
          <>
            <div className="ec-demo-toolbar">
              <div className="ec-demo-tabs" role="tablist" aria-label="Ticker">
                {tickers.map((t, i) => (
                  <button
                    key={t.ticker}
                    type="button"
                    role="tab"
                    aria-selected={i === activeIndex}
                    className={`ec-demo-tab${i === activeIndex ? " is-active" : ""}`}
                    onClick={() => {
                      setActiveIndex(i);
                      setHoverIndex(null);
                    }}
                  >
                    {t.ticker}
                  </button>
                ))}
              </div>
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
            </div>

            <div className="ec-demo-legend">
              <span className="ec-demo-legend-item">
                <span className="ec-demo-dot" aria-hidden="true" />
                {ticker.name} <span className="ec-demo-symbol">{ticker.ticker}</span>
                <span className={`ec-chart-change${isUp ? " is-up" : " is-down"}`}>
                  {isUp ? "▲" : "▼"} {Math.abs(changePct).toFixed(1)}%
                </span>
              </span>
            </div>

            <svg
              ref={svgRef}
              className="ec-chart-svg"
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              onMouseMove={handleMove}
              onMouseLeave={() => setHoverIndex(null)}
              role="img"
              aria-label={`${
                chartType === "candle" ? "Candlestick" : chartType === "area" ? "Area" : "Line"
              } chart for ${ticker.name}`}
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

              {chartType === "area" && <path d={areaPath} className="ec-demo-area" />}
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

            {hovered && (
              <div className="ec-chart-tooltip">
                <span className="ec-chart-tooltip-date">{hoveredLabel}</span>
                <span>O {hovered.open.toFixed(1)}</span>
                <span>H {hovered.high.toFixed(1)}</span>
                <span>L {hovered.low.toFixed(1)}</span>
                <span>C {hovered.close.toFixed(1)}</span>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

export default DemoChart;
