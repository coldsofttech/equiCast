import "./ServiceUnavailableIcon.css";

/** One row of candlesticks — the same shape every real chart in equiCast
 * draws bars with — greyed out and pulsing in a left-to-right sweep, like
 * a heartbeat monitor searching for a signal. Used for ServiceUnavailablePage:
 * the market's still "there," it's just not reaching us right now. */
const CANDLES = [
  { x: 20, wickTop: 18, wickBottom: 92, bodyY: 44, bodyH: 22 },
  { x: 44, wickTop: 12, wickBottom: 86, bodyY: 32, bodyH: 30 },
  { x: 68, wickTop: 24, wickBottom: 96, bodyY: 50, bodyH: 18 },
  { x: 92, wickTop: 16, wickBottom: 88, bodyY: 38, bodyH: 26 },
  { x: 116, wickTop: 20, wickBottom: 94, bodyY: 48, bodyH: 20 },
];

function ServiceUnavailableIcon() {
  return (
    <svg viewBox="0 0 136 110" fill="none" xmlns="http://www.w3.org/2000/svg">
      {CANDLES.map((c, i) => (
        <g
          key={c.x}
          className="ec-erricon-503-candle"
          style={{ animationDelay: `${i * 0.15}s` }}
        >
          <line
            x1={c.x}
            y1={c.wickTop}
            x2={c.x}
            y2={c.wickBottom}
            stroke="var(--ec-text-subtle)"
            strokeWidth="2"
          />
          <rect x={c.x - 6} y={c.bodyY} width="12" height={c.bodyH} rx="2" fill="var(--ec-text-subtle)" />
        </g>
      ))}
    </svg>
  );
}

export default ServiceUnavailableIcon;
