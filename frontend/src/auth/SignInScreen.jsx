import { useRef } from "react";
import CandlestickSpearIcon from "../components/brand/CandlestickSpearIcon.jsx";
import PublicHeader from "../components/shell/PublicHeader.jsx";
import SiteFooter from "../components/shell/SiteFooter.jsx";
import DemoChart from "./DemoChart.jsx";
import { DiversificationMockup, PerformanceMockup, PortfolioPiesMockup } from "./FeatureMockups.jsx";
import RoadmapCarousel from "./RoadmapCarousel.jsx";
import "./SignInScreen.css";

// The half-dozen features spotlighted as full alternating rows — picked for
// visual richness/differentiation, not just chronological/alphabetical
// order. Everything else implemented lives in STRIP_FEATURES below instead.
const SPOTLIGHT_FEATURES = [
  {
    title: "UK dividend tax & allowance",
    desc: "GIA dividends are taxed automatically against your income band, with the UK allowance tracked per tax year on its own page. ISA, SIPP, LISA and JISA holdings stay untaxed by design, so only the dividends that actually owe tax ever touch the calculation — you always know what's really yours.",
    visual: "icon",
    icon: (
      <svg viewBox="0 0 20 20" width="32" height="32" fill="none" aria-hidden="true">
        <path
          d="M10 2.5l6 2.2v4.3c0 4-2.6 6.9-6 8.3-3.4-1.4-6-4.3-6-8.3V4.7L10 2.5z"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinejoin="round"
        />
        <path d="M7 10l2 2 4-4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: "Portfolio pies",
    desc: "Split an account into custom pies to see exactly how your money is allocated. Give a growth pie and a dividend pie their own holdings within the same account, and track each one's value and weighting on its own, without spreading them across separate logins.",
    visual: "mockup",
    mockup: <PortfolioPiesMockup />,
  },
  {
    title: "Risk & valuation metrics",
    desc: "Volatility, Sharpe ratio, max drawdown and CAGR from 1 to 10 years — computed for every ticker you follow, so you can weigh a holding's return against the actual risk it took to get there.",
    visual: "icon",
    icon: (
      <svg viewBox="0 0 20 20" width="32" height="32" fill="none" aria-hidden="true">
        <path d="M4 16V9M10 16V4M16 16v-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: "Diversification & benchmarking",
    desc: "See your sector breakdown and how your portfolio stacks up against a benchmark, with drill-down into industry-level detail. Spot concentration building up in a single sector before it becomes a problem, and see it against a benchmark you choose, not a one-size-fits-all index.",
    visual: "mockup",
    mockup: <DiversificationMockup />,
  },
  {
    title: "Goals & funding targets",
    desc: "Set savings goals, map them to accounts or pies, and track progress automatically. Whether it's a house deposit or a retirement pot, link a goal to whatever's funding it and watch the progress move as you invest — no manual updates, no separate tracker.",
    visual: "icon",
    icon: (
      <svg viewBox="0 0 20 20" width="32" height="32" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.4" />
        <circle cx="10" cy="10" r="3.6" stroke="currentColor" strokeWidth="1.3" />
        <circle cx="10" cy="10" r="0.9" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: "Since-inception performance",
    desc: "See invested vs. current value across your whole history, not just today's snapshot. It's the number that actually matters for long-term investing — how far you've come since day one, not the day-to-day noise in between.",
    visual: "mockup",
    mockup: <PerformanceMockup />,
  },
];

// The rest of what's implemented, shown as a lighter-weight strip beneath
// the spotlights rather than another 6 full-size cards.
const STRIP_FEATURES = [
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
    title: "Daily equity & FX data",
    desc: "Pricing for stocks, ETFs, FX pairs and benchmarks, kept ready to query.",
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
    title: "Dividends & corporate events",
    desc: "Ex-dividend dates, earnings and withholding tax rates, tracked automatically.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <rect x="2.5" y="3.5" width="15" height="14" rx="2" stroke="currentColor" strokeWidth="1.6" />
        <path d="M2.5 7.5h15" stroke="currentColor" strokeWidth="1.6" />
        <path d="M6 2v3M14 2v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: "Import Transactions",
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
  {
    title: "Buy/sell ratings",
    desc: "See the current analyst consensus — buy or sell — for every ticker you follow.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <path d="M6 13V7M6 7L3.5 9.5M6 7l2.5 2.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M14 7v6M14 13l2.5-2.5M14 13l-2.5-2.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: "Transaction-level tracking",
    desc: "View a position's average cost basis, or drill into every individual buy and sell.",
    icon: (
      <svg viewBox="0 0 20 20" width="20" height="20" fill="none" aria-hidden="true">
        <path d="M4 5.5h12M4 10h12M4 14.5h8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
  },
];

// The fuller product vision — what equiCast is being built toward, not what's
// available today (see SPOTLIGHT_FEATURES/STRIP_FEATURES above for that).
// Each group's items are the visualisation/analysis layer on top of data
// equiCast already collects, not a restatement of the raw-data items above
// — deliberately kept distinct so the sections don't repeat each other.
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
      "Analyst price targets",
      "Screeners to surface top performers by sector or growth",
    ],
  },
  {
    tag: "Income & tax",
    title: "Dividend income & UK tax",
    items: [
      "Consolidated 5-year income projections, not just per-payout totals",
      "Capital gains tax, with a household-level view",
      "Cumulative income visualised across your whole portfolio",
    ],
  },
  {
    tag: "Unique to equiCast",
    title: "Portfolio intelligence",
    items: [
      "Custom watchlists",
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
      "Broker-linked import, plus splits, spin-offs and other corporate actions",
      "Fully responsive layouts for phone and tablet",
    ],
  },
];

/** A repeated conversion prompt for visitors who scroll past the hero without signing in. */
function CtaBanner({ title, sub, onSignIn }) {
  return (
    <div className="ec-cta-banner">
      <h3>{title}</h3>
      <p>{sub}</p>
      <button type="button" className="ec-signin-btn" onClick={onSignIn} disabled={!onSignIn}>
        Log in
        <svg className="ec-signin-btn-arrow" viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
          <path d="M4 10h12M11 5l5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </div>
  );
}

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
              One place to track multi-currency portfolios, daily equity &amp; FX data, and the
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
              Secured by Auth0 — by signing in you agree to the{" "}
              <a href="https://www.okta.com/legal/terms-of-service/" target="_blank" rel="noopener noreferrer">
                Terms
              </a>{" "}
              and{" "}
              <a href="https://www.okta.com/legal/privacy-policy/" target="_blank" rel="noopener noreferrer">
                Privacy Notice
              </a>
              .
            </p>
          </div>

          <div className="ec-hero-visual" aria-hidden="true">
            <span className="ec-hero-chip ec-hero-chip--1">Stocks</span>
            <span className="ec-hero-chip ec-hero-chip--2 ec-hero-chip--accent">ETFs</span>
            <span className="ec-hero-chip ec-hero-chip--3 ec-hero-chip--purple">FX</span>
            <span className="ec-hero-chip ec-hero-chip--4">Portfolios</span>
            <span className="ec-hero-chip ec-hero-chip--5 ec-hero-chip--accent">Forecasting</span>
            <span className="ec-hero-chip ec-hero-chip--6 ec-hero-chip--purple">Analytics</span>
            <span className="ec-hero-chip ec-hero-chip--7">Benchmarks</span>
            <span className="ec-hero-chip ec-hero-chip--8 ec-hero-chip--accent">Volatility</span>
            <span className="ec-hero-chip ec-hero-chip--9 ec-hero-chip--purple">CAGR</span>
            <span className="ec-hero-chip ec-hero-chip--10">Dividends</span>
            <span className="ec-hero-chip ec-hero-chip--11 ec-hero-chip--accent">Taxation</span>
            <span className="ec-hero-chip ec-hero-chip--12 ec-hero-chip--purple">Goals</span>
            <span className="ec-hero-chip ec-hero-chip--13">Transactions</span>
            <span className="ec-hero-chip ec-hero-chip--14 ec-hero-chip--accent">Diversification</span>
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
        <span className="ec-section-eyebrow">Available today</span>
        <h2 className="ec-features-title">Everything your portfolio needs, one login away.</h2>

        <div className="ec-spotlight-list">
          {SPOTLIGHT_FEATURES.map((feature, index) => (
            <div
              className={`ec-spotlight-row${index % 2 === 1 ? " ec-spotlight-row--reverse" : ""}`}
              key={feature.title}
            >
              <div className="ec-spotlight-visual">
                {feature.visual === "icon" ? (
                  <div className="ec-spotlight-icon-panel">{feature.icon}</div>
                ) : (
                  feature.mockup
                )}
              </div>
              <div className="ec-spotlight-copy">
                <h3>{feature.title}</h3>
                <p>{feature.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="ec-feature-strip">
          {STRIP_FEATURES.map((feature) => (
            <div className="ec-feature-strip-item" key={feature.title}>
              <span className="ec-feature-strip-icon">{feature.icon}</span>
              <div>
                <h4>{feature.title}</h4>
                <p>{feature.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <CtaBanner
          title="Ready to see your own portfolio like this?"
          sub="Sign in and set up your accounts in minutes — no card, no commitment."
          onSignIn={onSignIn}
        />
      </section>

      <DemoChart />

      <section className="ec-roadmap">
        <span className="ec-section-eyebrow">Coming next</span>
        <h2 className="ec-features-title">The best of the tools you already use, in one place.</h2>
        <p className="ec-roadmap-sub">
          Core accounts, market data and risk metrics are available today — here&rsquo;s everywhere
          equiCast is headed next.
        </p>
        <RoadmapCarousel groups={ROADMAP} />

        <CtaBanner
          title="Don’t wait for the roadmap to get started"
          sub="Accounts, dividends, risk metrics and more are already available today — sign in and start tracking your own portfolio now."
          onSignIn={onSignIn}
        />
      </section>

      <SiteFooter />
    </div>
  );
}

export default SignInScreen;
