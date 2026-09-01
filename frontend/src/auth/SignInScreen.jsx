import { useRef } from "react";
import Logo from "../components/brand/Logo.jsx";
import CandlestickSpearIcon from "../components/brand/CandlestickSpearIcon.jsx";
import ThemeToggle from "../components/shell/ThemeToggle.jsx";
import SiteFooter from "../components/shell/SiteFooter.jsx";
import DemoChart from "./DemoChart.jsx";
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
    desc: "Pricing for stocks, ETFs and FX pairs, kept ready to query.",
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
    title: "Risk & valuation metrics",
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
];

// The fuller product vision — what equiCast is being built toward, not what's
// live today (see FEATURES above for that). Each group's items are the
// visualisation/analysis layer on top of data equiCast already collects, not
// a restatement of the raw-data items in FEATURES — deliberately kept
// distinct so the two sections don't repeat each other.
const ROADMAP = [
  {
    tag: "Data & news",
    title: "Markets, at a glance",
    items: [
      "Market indices, sector and top-mover overviews",
      "A news feed curated to your holdings",
      "A calendar for macro events — rate decisions, inflation prints and more",
    ],
  },
  {
    tag: "Analysis tools",
    title: "Fundamentals & screening",
    items: [
      "Company fundamentals, financials and key statistics",
      "Analyst ratings and price targets",
      "Screeners to surface top performers by sector or growth",
    ],
  },
  {
    tag: "Income tracking",
    title: "Dividend income",
    items: [
      "A payout calendar with 5-year income projections",
      "Dividend growth history and yield tracking",
      "Cumulative income visualised across your whole portfolio",
    ],
  },
  {
    tag: "Unique to equiCast",
    title: "Portfolio intelligence",
    items: [
      "Custom “pies” to visualise portfolio composition",
      "Forecasts and a future-value growth simulator",
      "A performance heatmap across every holding",
    ],
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
            <span className="ec-hero-eyebrow">Forecasting</span>
            <h1 className="ec-hero-title">Cast your equity forward.</h1>
            <p className="ec-hero-sub">
              One place to track multi-currency portfolios, live equity &amp; FX data, and the
              risk metrics behind every ticker you follow — with forecasting on the way.
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
            <span className="ec-hero-chip ec-hero-chip--4">Portfolios</span>
            <span className="ec-hero-chip ec-hero-chip--5">Forecasting</span>
            <span className="ec-hero-chip ec-hero-chip--6">Analytics</span>
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
        <span className="ec-section-eyebrow">Live today</span>
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

      <DemoChart />

      <section className="ec-roadmap">
        <span className="ec-section-eyebrow">Coming next</span>
        <h2 className="ec-features-title">The best of the tools you already use, in one place.</h2>
        <p className="ec-roadmap-sub">
          Core accounts, market data and risk metrics are live today — here&rsquo;s everywhere
          equiCast is headed next.
        </p>
        <div className="ec-roadmap-grid">
          {ROADMAP.map((group) => (
            <div className="ec-roadmap-card" key={group.title}>
              <span className="ec-roadmap-tag">{group.tag}</span>
              <h3>{group.title}</h3>
              <ul className="ec-roadmap-list">
                {group.items.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}

export default SignInScreen;
