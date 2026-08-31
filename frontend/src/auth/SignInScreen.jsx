import { useRef } from "react";
import Logo from "../components/brand/Logo.jsx";
import CandlestickSpearIcon from "../components/brand/CandlestickSpearIcon.jsx";
import ThemeToggle from "../components/shell/ThemeToggle.jsx";
import "./SignInScreen.css";

const FEATURES = [
  {
    title: "Multi-currency accounts",
    desc: "Hold and track investment accounts across currencies, valued consistently in one place.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <rect x="2.5" y="5.5" width="15" height="10" rx="2" stroke="currentColor" strokeWidth="1.6" />
        <path d="M2.5 8.5h15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="14" cy="12.2" r="1.3" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: "Live equity & FX data",
    desc: "Pricing for stocks, ETFs and FX pairs, sourced from Yahoo Finance and kept ready to query.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <path
          d="M2.5 14.5l4-5 3 3.2 4.5-6.2 3.5 4.6"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="17.5" cy="10.1" r="1.2" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: "Forecasting & risk metrics",
    desc: "Volatility, Sharpe ratio, max drawdown and CAGR — computed for every ticker you follow.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <path d="M4 16V9M10 16V4M16 16v-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: "Dividends & corporate events",
    desc: "Ex-dividend dates, earnings, rating changes and splits, tracked automatically.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <rect x="2.5" y="3.5" width="15" height="14" rx="2" stroke="currentColor" strokeWidth="1.6" />
        <path d="M2.5 7.5h15" stroke="currentColor" strokeWidth="1.6" />
        <path d="M6 2v3M14 2v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: "Custom watchlists",
    desc: "Follow the tickers and pairs that matter to you, without the noise of everything else.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <path
          d="M10 3.5l2.1 4.3 4.7.7-3.4 3.3.8 4.7-4.2-2.2-4.2 2.2.8-4.7-3.4-3.3 4.7-.7z"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    title: "Secured by Auth0",
    desc: "Your accounts and holdings are gated behind real authentication — yours alone to see.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <path
          d="M10 2.5l6 2.2v4.6c0 4-2.6 6.8-6 8.2-3.4-1.4-6-4.2-6-8.2V4.7z"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinejoin="round"
        />
        <path d="M7.5 10l1.8 1.8L13 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
];

/**
 * `onSignIn` is `loginWithRedirect` from useAuth0(), passed in by
 * RequireAuth rather than called here directly — keeps this component
 * presentation-only (also makes it trivial to render/test without an
 * Auth0Provider in scope). It's `undefined` in the "Auth0 isn't configured"
 * state, so the CTA is disabled rather than silently doing nothing.
 */
function SignInScreen({ onSignIn, error }) {
  const featuresRef = useRef(null);

  const scrollToFeatures = () => {
    featuresRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="ec-landing">
      <div className="ec-hero">
        <div className="ec-hero-glow" aria-hidden="true" />
        <header className="ec-landing-bar">
          <Logo />
          <ThemeToggle />
        </header>

        <div className="ec-hero-grid">
          <div className="ec-hero-copy">
            <span className="ec-hero-eyebrow">Equity + FX forecasting</span>
            <h1 className="ec-hero-title">Cast your equity forward.</h1>
            <p className="ec-hero-sub">
              One place to track multi-currency portfolios, live equity &amp; FX data, and
              forecasts built on real risk metrics — not spreadsheets.
            </p>
            {error ? (
              <p className="ec-signin-error" role="alert">
                {error}
              </p>
            ) : null}
            <div className="ec-hero-actions">
              <button type="button" className="ec-signin-btn" onClick={onSignIn} disabled={!onSignIn}>
                Log in
                <svg className="ec-signin-btn-arrow" viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
                  <path
                    d="M4 10h12M11 5l5 5-5 5"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>
              <button type="button" className="ec-hero-learn" onClick={scrollToFeatures}>
                What&rsquo;s inside
              </button>
            </div>
            <p className="ec-hero-fine">
              Secured by Auth0 — by signing in you agree to the Terms and Privacy Notice.
            </p>
          </div>

          <div className="ec-hero-visual" aria-hidden="true">
            <span className="ec-hero-chip ec-hero-chip--1">Stocks</span>
            <span className="ec-hero-chip ec-hero-chip--2">ETFs</span>
            <span className="ec-hero-chip ec-hero-chip--3">FX</span>
            <div className="ec-hero-badge">
              <CandlestickSpearIcon size={40} />
            </div>
            <p className="ec-hero-quote">
              Every account, every currency —{" "}
              <span className="ec-hero-quote-highlight">one forecast</span>.
            </p>
          </div>
        </div>

        <button
          type="button"
          className="ec-hero-scroll-cue"
          onClick={scrollToFeatures}
          aria-label="Scroll to learn more about equiCast"
        >
          <svg viewBox="0 0 20 20" width="18" height="18" fill="none" aria-hidden="true">
            <path d="M5 8l5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

      <section className="ec-features" ref={featuresRef}>
        <h2 className="ec-features-title">Everything your portfolio needs, one login away.</h2>
        <div className="ec-feature-grid">
          {FEATURES.map((feature) => (
            <div className="ec-feature-card" key={feature.title}>
              <span className="ec-feature-icon">{feature.icon}</span>
              <h3>{feature.title}</h3>
              <p>{feature.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="ec-landing-foot">
        <Logo compact />
        <span>© {new Date().getFullYear()} equiCast</span>
      </footer>
    </div>
  );
}

export default SignInScreen;
