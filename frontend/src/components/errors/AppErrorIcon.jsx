import "./AppErrorIcon.css";

/** A single, larger candle in the danger tone, cracked through the
 * middle — the same wick+body shape the brand mark's own Candlestick
 * Spear icon uses, distressed rather than swapped for a generic
 * broken-robot/bug glyph. Shakes once on mount (an unexpected crash just
 * happened) and settles — a continuous shake would be distracting on a
 * page someone might sit with while reloading. */
function AppErrorIcon() {
  return (
    <svg
      viewBox="0 0 100 110"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="ec-erricon-apperror"
    >
      <line x1="50" y1="8" x2="50" y2="102" stroke="var(--ec-danger)" strokeWidth="3" />
      <rect
        x="28"
        y="33"
        width="44"
        height="44"
        rx="5"
        fill="var(--ec-danger-soft)"
        stroke="var(--ec-danger)"
        strokeWidth="3"
      />
      <path
        d="M36,33 L48,55 L39,59 L60,77"
        stroke="var(--ec-danger)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default AppErrorIcon;
