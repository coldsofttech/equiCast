import { useEffect, useState } from "react";
import Logo from "../components/brand/Logo.jsx";
import "./AppLoadingScreen.css";

/** Candlestick bars that grow up from the baseline in a staggered wave,
 * looping — equiCast's own chart visual language (see e.g.
 * ServiceUnavailableIcon.jsx's pulsing row), here reading as "building"
 * rather than "searching for a signal". */
const CANDLES = [
  { x: 20, bodyH: 30 },
  { x: 44, bodyH: 52 },
  { x: 68, bodyH: 22 },
  { x: 92, bodyH: 44 },
  { x: 116, bodyH: 36 },
];
const BASELINE_Y = 92;

function LoadingIcon() {
  return (
    <svg viewBox="0 0 136 110" fill="none" xmlns="http://www.w3.org/2000/svg">
      {CANDLES.map((c, i) => (
        <g
          key={c.x}
          className="ec-apploading-candle"
          style={{ animationDelay: `${i * 0.12}s`, transformOrigin: `${c.x}px ${BASELINE_Y}px` }}
        >
          <line
            x1={c.x}
            y1={BASELINE_Y - c.bodyH - 14}
            x2={c.x}
            y2={BASELINE_Y}
            stroke="var(--ec-accent)"
            strokeWidth="2"
          />
          <rect
            x={c.x - 6}
            y={BASELINE_Y - c.bodyH}
            width="12"
            height={c.bodyH}
            rx="2"
            fill="var(--ec-accent)"
          />
        </g>
      ))}
    </svg>
  );
}

/** Cycled every `intervalMs`, fading out/in between — deliberately generic
 * ("your accounts", "your portfolio value") rather than naming every
 * concrete thing this screen might end up waiting on, so this doesn't need
 * updating every time another data source is added to the gate below. */
const LOADING_MESSAGES = [
  "Loading your accounts…",
  "Checking your portfolio value…",
  "Warming up FX rates…",
  "Almost there…",
];

/**
 * Full-screen "app is getting ready" overlay — no AppShell/Topbar, same
 * standalone-full-viewport convention ErrorPage.jsx uses, since what this
 * screen is waiting on (accounts, FX rates) is exactly what Topbar's own
 * currency/balance chrome would otherwise need too. Shown by DashboardPage
 * while its accounts fetch and the login-time FX warm-up (GitHub issues
 * #149/#177, see utils/fxWarmup.js) are both still in flight — real work
 * happening underneath, not a fake delay; this only exists to make that
 * wait feel like something rather than a blank page.
 *
 * The rotating message is cosmetic only: it doesn't track which of those
 * two loads has actually finished, just cycles on a timer for the whole
 * time this is mounted, since the two independent fetches don't have
 * fine-grained enough shared state to narrate honestly step by step.
 */
function AppLoadingScreen() {
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 1600);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="ec-apploading">
      <div className="ec-apploading-logo">
        <Logo />
      </div>
      <div className="ec-apploading-body">
        <div className="ec-apploading-icon" aria-hidden="true">
          <LoadingIcon />
        </div>
        <h1 className="ec-apploading-title">Getting everything ready</h1>
        <p className="ec-apploading-message" key={messageIndex} role="status">
          {LOADING_MESSAGES[messageIndex]}
        </p>
      </div>
    </div>
  );
}

export default AppLoadingScreen;
