import { useRef } from "react";
import CandlestickSpearIcon from "../components/brand/CandlestickSpearIcon.jsx";
import PublicHeader from "../components/shell/PublicHeader.jsx";
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
    title: "Portfolio pies",
    desc: "Split an account into custom pies to see exactly how your money is allocated.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.6" />
        <path d="M10 10V3.2A6.8 6.8 0 0116.8 10z" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: "Goals & funding targets",
    desc: "Set savings goals, map them to accounts or pies, and track progress automatically.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.6" />
        <circle cx="10" cy="10" r="3.6" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="10" cy="10" r="0.9" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: "Since-inception performance",
    desc: "See invested vs. current value across your whole history, not just today's snapshot.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <path
          d="M2.5 15.5c2.5 0 2.5-8 5-8s2.5 5.5 5 5.5 2.5-6.5 5-6.5"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    title: "Import from CSV or Trading 212",
    desc: "Bring in your existing transaction history in minutes — no manual re-entry.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <path
          d="M10 13V3.5M6.5 6.5L10 3l3.5 3.5"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path d="M3 13.5v1.8a1.7 1.7 0 001.7 1.7h10.6a1.7 1.7 0 001.7-1.7v-1.8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
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
      "A news feed curated to your holdings, with sentiment scoring",
      "A calendar for macro events — rate decisions, inflation prints and more",
    ],
  },
  {
    tag: "Analysis tools",
    title: "Fundamentals & screening",
    items: [
      "Company financials and key statistics for every holding",
      "Analyst ratings and price targets",
      "Screeners to surface top performers by sector or growth",
    ],
  },
  {
    tag: "Income & tax",
    title: "Dividend income & UK tax",
    items: [
      "A payout calendar with 5-year income projections",
      "UK dividend allowance and capital gains tax, with a household-level view",
      "Cumulative income visualised across your whole portfolio",
    ],
  },
  {
    tag: "Unique to equiCast",
    title: "Portfolio intelligence",
    items: [
      "Custom watchlists for tickers you don't hold yet",
      "Forecasts and a future-value growth simulator",
      "Sold-candidate and rebalancing suggestions",
      "Smarter sector-diversification and benchmark-comparison scoring",
    ],
  },
  {
    tag: "Coverage & access",
    title: "More to track, everywhere you are",
    items: [
      "Futures, alongside stocks, ETFs and FX",
      "Broker-linked import (starting with Trading 212), plus splits, spin-offs and other corporate actions",
      "Fully responsive layouts for phone and tablet",
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
      <PublicHeader />

      <div className="ec-hero">
        <div className="ec-hero-glow" aria-hidden="true" />

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
