import { useAuth0 } from "@auth0/auth0-react";
import AppShell from "../components/shell/AppShell.jsx";
import PublicHeader from "../components/shell/PublicHeader.jsx";
import SiteFooter from "../components/shell/SiteFooter.jsx";
import "./PrivacyPolicyPage.css";

const LAST_UPDATED = "Last updated 10 September 2026.";

/**
 * Public — not behind RequireAuth (see App.jsx) — since a visitor has to
 * be able to read this before ever signing in. Two different layouts: a
 * signed-out visitor gets `PublicHeader` (no AppShell/Topbar, which
 * assumes a signed-in profile — same reason the error pages are
 * standalone, see components/errors/ErrorPage.jsx; `PublicHeader` is the
 * same shared header SignInScreen/TermsAndConditionsPage use, so the logo
 * sits pixel-identically across every signed-out page), while a signed-in
 * visitor (e.g. following the footer link from inside the app) gets the
 * real AppShell — Topbar plus the same `stickyTitle` frozen-title-bar
 * treatment AccountDetailPage/PieDetailPage/HoldingTickerPage use, so
 * "Privacy Policy" stays visible while scrolling through this long a
 * page, the same as an account/pie name does on those pages.
 *
 * Every item named below is real — grounded in what equiCast's own code
 * actually collects/stores (Auth0 for sign-in identity; S3 JSON for
 * accounts/pies/watchlists/holdings/transactions; DynamoDB for the
 * default_currency/transaction_type profile settings; localStorage/
 * sessionStorage/IndexedDB for session/preference/offline caching — see
 * equicast_core's various *Client classes and frontend/src/utils/) — not
 * generic legal boilerplate. This is still a plain-language summary, not
 * a substitute for legal review before being relied on.
 */
function PrivacyPolicyPage() {
  const { isAuthenticated } = useAuth0();

  const content = (
    <>
        <p>
          This page explains what personal and financial data equiCast collects when you use it,
          why, where it's stored, and who (if anyone) it's shared with. equiCast is an
          open-source, self-hosted-style project rather than a company with a dedicated privacy
          team, so this is written in plain language rather than formal legal terms — see{" "}
          <a href="https://github.com/coldsofttech/equiCast">equiCast's GitHub repository</a> for
          the actual source code this page describes.
        </p>

        <h2>Information we collect</h2>
        <p>
          When you sign in, equiCast uses <a href="https://auth0.com/privacy">Auth0</a> to
          authenticate you and receives your name, email address, and profile picture from
          whichever identity provider you sign in with — this is what's shown in the account menu
          and greeting. Auth0 assigns you a stable user ID, which equiCast uses internally to
          associate your own data with you, without storing your password itself (Auth0 handles
          that entirely).
        </p>
        <p>
          Everything else equiCast stores is data you explicitly enter while using it: the
          accounts, pies, watchlists, and holdings you create, the buy/sell/dividend transactions
          you record against them, and your default currency and transaction-recording preference.
          None of this is inferred or collected passively — it's only ever what you type into the
          app yourself.
        </p>

        <h2>How we use it</h2>
        <p>
          Your data is used solely to run the app for you: authenticating you, showing your own
          accounts/pies/holdings back to you, computing their current value/profit-loss/dividend
          totals against published market data, and remembering your currency/transaction-type
          preferences. equiCast doesn't use your data for advertising, doesn't build a profile of
          you beyond what's needed to show you your own portfolio, and doesn't use it to train any
          model.
        </p>

        <h2>Where it's stored</h2>
        <p>
          Your accounts/pies/watchlists/holdings/transactions are stored as your own private,
          access-controlled records on Amazon Web Services (AWS) — S3 for the records themselves,
          DynamoDB for your currency/transaction-type profile settings — in AWS's{" "}
          <code>eu-west-1</code> (Ireland) region by default. Every request between your browser
          and equiCast's servers is made over HTTPS. equiCast also caches some of this locally on
          your own device (browser <code>localStorage</code>/<code>sessionStorage</code>/
          <code>IndexedDB</code>) purely so pages load quickly without re-fetching everything —
          this cache never leaves your device.
        </p>

        <h2>Who we share it with</h2>
        <p>
          equiCast shares data with exactly two outside parties, both because the app can't
          function without them: <a href="https://auth0.com/privacy">Auth0</a> (authentication —
          receives your login credentials directly, never equiCast) and AWS (hosting — stores the
          data described above). Market, dividend, and corporate-events data flows the other
          direction only — equiCast reads published data from Yahoo Finance (via the open-source{" "}
          <code>yfinance</code> library) to value your holdings; none of your own account or
          transaction data is ever sent to Yahoo Finance or any other market-data source. equiCast
          runs no analytics or advertising services today, and never sells, rents, or otherwise
          trades your data to any third party.
        </p>

        <h2>Deleting your data</h2>
        <p>
          Deleting an account (from the Accounts page) permanently removes that account and,
          with it, every pie/holding/transaction recorded under it — this happens immediately,
          not on a delay. Deleting every account you have removes essentially all of your
          portfolio data. To have your Auth0 identity and remaining profile settings erased
          entirely, open an issue on{" "}
          <a href="https://github.com/coldsofttech/equiCast/issues">
            equiCast's GitHub repository
          </a>{" "}
          — there's no self-service "delete my account" button for identity data yet, since
          equiCast has no dedicated support inbox to route that request to otherwise.
        </p>

        <h2>Your rights</h2>
        <p>
          You can ask to see a copy of the data equiCast holds about you, have it corrected, or
          have it deleted, at any time — use the GitHub issues link above for anything the app
          itself doesn't already let you do directly (editing/deleting an account, pie, holding,
          or transaction yourself, right in the app, is usually faster than asking).
        </p>

        <h2>Children</h2>
        <p>
          equiCast isn't directed at children, and doesn't knowingly collect data from anyone
          under 16. If you believe a child has created an account, contact us via the GitHub
          issues link above and we'll remove it.
        </p>

        <h2>Changes to this policy</h2>
        <p>
          If what equiCast collects or how it's used changes, this page will be updated and its
          "Last updated" date above will change accordingly — there's no separate notification
          mechanism today beyond checking back here.
        </p>

        <h2>Questions</h2>
        <p>
          equiCast is an open-source project — if anything on this page is unclear, or you think
          something here doesn't match what the app actually does, open an issue on{" "}
          <a href="https://github.com/coldsofttech/equiCast/issues">
            equiCast's GitHub repository
          </a>
          .
        </p>
    </>
  );

  if (isAuthenticated) {
    return (
      <AppShell title="Privacy Policy" subtitle={LAST_UPDATED} stickyTitle narrow footer={<SiteFooter />}>
        <div className="ec-privacypolicy-body ec-privacypolicy-body--shell">{content}</div>
      </AppShell>
    );
  }

  return (
    <div className="ec-privacypolicy">
      <PublicHeader />

      <main className="ec-privacypolicy-body">
        <h1>Privacy Policy</h1>
        <p className="ec-privacypolicy-updated">{LAST_UPDATED}</p>
        {content}
      </main>

      <SiteFooter />
    </div>
  );
}

export default PrivacyPolicyPage;
