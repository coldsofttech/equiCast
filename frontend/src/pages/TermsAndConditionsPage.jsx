import { Link } from "react-router-dom";
import Logo from "../components/brand/Logo.jsx";
import SiteFooter from "../components/shell/SiteFooter.jsx";
import "./TermsAndConditionsPage.css";

/**
 * Public — not behind RequireAuth (see App.jsx) — since a visitor has to
 * be able to read this before ever signing in. Standalone layout (no
 * AppShell/Topbar, which assumes a signed-in profile), same reason
 * PrivacyPolicyPage.jsx is standalone.
 *
 * Grounded in what equiCast actually is and does — an open-source (MIT,
 * see the repo's LICENSE), self-hosted-style portfolio tracker with no
 * registered company behind it — and in the same no-advice/data-source
 * disclaimer SiteFooter already carries on every authenticated page,
 * rather than generic legal boilerplate (no invented governing-law/
 * arbitration clauses this project has no real jurisdiction/entity to
 * back up). This is still a plain-language summary, not a substitute for
 * legal review before being relied on.
 */
function TermsAndConditionsPage() {
  return (
    <div className="ec-terms">
      <header className="ec-terms-head">
        <Link to="/" className="ec-terms-logo-link" aria-label="Go to equiCast">
          <Logo />
        </Link>
      </header>

      <main className="ec-terms-body">
        <h1>Terms and Conditions</h1>
        <p className="ec-terms-updated">Last updated 10 September 2026.</p>

        <p>
          By using equiCast, you agree to these terms. equiCast is an open-source project (MIT
          licensed — see{" "}
          <a href="https://github.com/coldsofttech/equiCast/blob/main/LICENSE">the LICENSE file</a>{" "}
          in <a href="https://github.com/coldsofttech/equiCast">equiCast's GitHub repository</a>)
          rather than a company, so this is written in plain language rather than formal legal
          terms — see equiCast's own Privacy Policy for what data using it involves.
        </p>

        <h2>What equiCast is</h2>
        <p>
          equiCast is a portfolio-tracking and forecasting tool: you record the accounts, pies,
          and holdings you own, log buy/sell/dividend transactions against them, and equiCast
          values and charts them against published market data. It's built for long-term
          investment analysis, not intraday or high-frequency trading — market data refreshes on
          a periodic ingestion cycle (every 6 hours), not a live real-time feed.
        </p>

        <h2>Not financial advice</h2>
        <p>
          Nothing in equiCast is a recommendation to buy, sell, or hold any security or currency.
          equiCast is not a registered investment adviser or broker-dealer. Risk and valuation
          metrics such as volatility, Sharpe ratio, max drawdown, CAGR, and any benchmark
          comparison rating are calculated by equiCast itself where its market-data source
          (Yahoo Finance, via the open-source <code>yfinance</code> library) doesn't provide them
          directly, and aren't sourced from a licensed data provider or ratings agency — validate
          their accuracy independently before relying on them. Past performance or illustrative
          figures shown aren't indicative of future results. Always do your own research or
          consult a licensed financial advisor before making investment decisions.
        </p>

        <h2>Your account and data</h2>
        <p>
          You sign in via Auth0, and everything you record — accounts, pies, watchlists,
          holdings, and transactions — is yours: you can edit or delete it at any time, and
          deleting an account permanently removes everything recorded under it, immediately. See
          the Privacy Policy for exactly what's collected/stored and where. You're responsible for
          the accuracy of whatever you enter — equiCast has no way to verify it against your real
          brokerage or bank records.
        </p>

        <h2>Acceptable use</h2>
        <p>
          Use equiCast only for its intended purpose — tracking and analyzing your own portfolio.
          Don't attempt to bypass its rate limits or authentication, scrape or bulk-extract data
          from it, or use it to harm equiCast, its infrastructure, or other users. Since the
          source code is public, you're welcome to run your own copy under the terms of its MIT
          license instead.
        </p>

        <h2>No warranty, no guaranteed availability</h2>
        <p>
          equiCast is provided "as is," without warranty of any kind, to the extent permitted by
          law — the same "as is, without warranty" basis its MIT license already puts the
          underlying source code on. It's a project with no dedicated uptime commitment or support
          team, so there's no guarantee it'll always be available, error-free, or that your data
          will never be lost — keep your own records of anything important.
        </p>

        <h2>Changes to these terms</h2>
        <p>
          If these terms change, this page will be updated and its "Last updated" date above will
          change accordingly — there's no separate notification mechanism today beyond checking
          back here. Continuing to use equiCast after a change means you accept the updated terms.
        </p>

        <h2>Questions</h2>
        <p>
          equiCast is an open-source project — if anything on this page is unclear, open an issue
          on{" "}
          <a href="https://github.com/coldsofttech/equiCast/issues">
            equiCast's GitHub repository
          </a>
          .
        </p>
      </main>

      <SiteFooter />
    </div>
  );
}

export default TermsAndConditionsPage;
