import { Link } from "react-router-dom";
import Logo from "../components/brand/Logo.jsx";
import Button from "../components/core/Button.jsx";
import SiteFooter from "../components/shell/SiteFooter.jsx";
import { openCookiePreferences } from "../components/cookies/CookieBanner.jsx";
import "./CookiePolicyPage.css";

/**
 * Public — not behind RequireAuth (see App.jsx) — since a visitor has to
 * be able to read this before ever signing in, from the same cookie
 * banner shown on the logged-out sign-in screen. Standalone layout (no
 * AppShell/Topbar, which assumes a signed-in profile) for the same reason
 * the error pages are standalone — see components/errors/ErrorPage.jsx.
 *
 * Every item named below is real — grounded in what equiCast's own code
 * actually stores (localStorage for theme/hide-balances/the cookie choice
 * itself and Auth0's session cache; sessionStorage for per-tab caches;
 * IndexedDB for offline data caching; Auth0's own cookies on its own
 * domain during the sign-in redirect) — not generic legal boilerplate.
 * This is still a plain-language summary, not a substitute for legal
 * review before being relied on.
 */
function CookiePolicyPage() {
  return (
    <div className="ec-cookiepolicy">
      <header className="ec-cookiepolicy-head">
        <Link to="/" className="ec-cookiepolicy-logo-link" aria-label="Go to equiCast">
          <Logo />
        </Link>
      </header>

      <main className="ec-cookiepolicy-body">
        <h1>Cookie Policy</h1>
        <p className="ec-cookiepolicy-updated">Last updated 10 September 2026.</p>

        <p>
          This page explains what equiCast stores on your device, why, and how to change your
          mind. It covers cookies in the everyday sense (small values a website asks your browser
          to hold) as well as the two other browser storage technologies equiCast actually uses —
          <code>localStorage</code> and <code>IndexedDB</code> — since they serve the same purpose
          and deserve the same explanation.
        </p>

        <div className="ec-cookiepolicy-manage">
          <Button variant="primary" onClick={openCookiePreferences}>
            Manage your cookie preferences
          </Button>
        </div>

        <h2>Strictly necessary — always on</h2>
        <p>
          equiCast uses <a href="https://auth0.com/privacy">Auth0</a> to handle sign-in. When you
          sign in, Auth0 sets its own cookies on its own domain to run the login redirect, and
          equiCast caches your session in <code>localStorage</code> so you stay signed in across a
          page refresh instead of being sent back to the sign-in screen every time. equiCast also
          stores your cookie choice itself here, so you're not asked again every visit. None of
          this is optional — equiCast can't sign you in without it.
        </p>

        <h2>Functional — always on</h2>
        <p>
          equiCast remembers your theme (light/dark) and whether you've chosen to hide currency
          balances, both in <code>localStorage</code>, so they stay set across visits instead of
          resetting every time. It also caches your accounts, holdings, prices, dividends and
          market-data lookups — in <code>sessionStorage</code> for the current tab and{" "}
          <code>IndexedDB</code> for longer, across a tab close/reopen — purely so pages load
          instantly from what's already on your device instead of re-fetching everything from the
          API on every visit. None of this is shared with anyone else or used to track you across
          other websites; it only ever describes your own equiCast data, back to you.
        </p>

        <h2>Analytics — off by default</h2>
        <p>
          equiCast doesn't use analytics or advertising cookies today — there's no tracking
          pixel, no third-party analytics script, nothing measuring how you use the app beyond
          equiCast's own servers logging the requests your browser already has to make it work.
          The "Analytics" toggle in your preferences exists for if that ever changes; until it
          does, turning it on or off has no effect, and it defaults to off either way.
        </p>

        <h2>Changing your mind</h2>
        <p>
          Use the "Manage your cookie preferences" button above at any time to change your
          analytics choice. You can also clear everything equiCast has stored by clearing your
          browser's site data for this domain (cookies, local storage and IndexedDB together,
          under your browser's own privacy/site-settings) — doing so signs you out and resets
          your theme/hide-balances choice back to their defaults.
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
      </main>

      <SiteFooter />
    </div>
  );
}

export default CookiePolicyPage;
