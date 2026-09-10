import "./OfflineIcon.css";

/** Ascending bars built the same way as a candlestick body (rather than
 * a generic wifi glyph), greyed out with a plain slash through them —
 * each one very slowly, faintly lights up bottom-to-top ("trying") and
 * fades again, since there's genuinely nothing to reconnect to yet. */
const BARS = [
  { x: 20, height: 20 },
  { x: 42, height: 35 },
  { x: 64, height: 50 },
  { x: 86, height: 65 },
];

function OfflineIcon() {
  return (
    <svg viewBox="0 0 110 90" fill="none" xmlns="http://www.w3.org/2000/svg">
      {BARS.map((bar, i) => (
        <rect
          key={bar.x}
          x={bar.x - 7}
          y={80 - bar.height}
          width="14"
          height={bar.height}
          rx="3"
          fill="var(--ec-text-subtle)"
          className="ec-erricon-offline-bar"
          style={{ animationDelay: `${i * 0.25}s` }}
        />
      ))}
      <line
        x1="12"
        y1="14"
        x2="98"
        y2="78"
        stroke="var(--ec-text-subtle)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default OfflineIcon;
