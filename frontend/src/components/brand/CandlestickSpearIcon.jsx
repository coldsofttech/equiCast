/**
 * The finalized equiCast mark: three ascending OHLC candlesticks, the
 * tallest candle's upper wick sharpened into a spearpoint breaking past
 * the frame. See docs/design/logo-concepts-round3-final.html (Variant 2)
 * and docs/design/README.md for how this was chosen over the other three
 * directions in that round.
 *
 * Renders in `currentColor` (not a hardcoded white) so it can sit on the
 * gradient badge (see Logo.jsx, which sets color via
 * `var(--ec-text-on-accent)`) or anywhere else a single-color glyph is
 * useful, rather than assuming its own background.
 */
function CandlestickSpearIcon({ size = 24, className }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={className}
      fill="currentColor"
      aria-hidden="true"
    >
      <line x1="5.5" y1="14" x2="5.5" y2="19.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
      <rect x="4" y="15" width="3" height="3.4" rx="0.6" />
      <line x1="11" y1="9" x2="11" y2="19.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
      <rect x="9.5" y="11" width="3" height="6.6" rx="0.6" />
      <line x1="16.5" y1="17" x2="16.5" y2="19.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
      <rect x="15" y="8" width="3" height="9" rx="0.6" />
      <polygon points="15.6,8 17.4,8 16.5,2" />
    </svg>
  );
}

export default CandlestickSpearIcon;
