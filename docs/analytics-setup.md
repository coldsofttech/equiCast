# Analytics setup

How equiCast tracks usage: `frontend/src/utils/analytics.js` dynamically
loads Google Analytics 4 (`gtag.js`) client-side, gated on the visitor's
cookie-consent "Analytics" choice (`hasAnalyticsConsent()` in
`frontend/src/utils/cookieConsent.js`, set via `CookieBanner.jsx`/the
Cookie Policy page's "Manage your cookie preferences" button). This is the
reference for creating the GA4 property and wiring its value into the
repo; there's no `terraform.yml` equivalent for GA itself (see below).

## Why GA4, and why one shared property

Analytics exists to understand how the app is actually used (page views,
plus a handful of specific actions — see "What gets tracked" below), not
to identify individual visitors — equiCast has no user-level analytics
profile, and GA is entirely off unless a visitor opts in via the cookie
banner. One shared GA4 property for both `dev` and `prod`, same reasoning
as [Auth0's shared tenant](auth0-setup.md#why-auth0-and-why-one-shared-tenantapi):
there's no per-environment traffic split that matters yet (dev traffic is
mostly the people building the app), and running two properties would mean
switching GA context to check dev vs. prod. Revisit this split if dev
traffic ever meaningfully pollutes prod's numbers.

**Not Terraform-managed**: like Auth0, there's no Terraform provider wired
up for Google Analytics in this repo — the property and its web data
stream are created once, manually, in the GA dashboard, and only the
resulting Measurement ID flows into the repo as a plain env var.

**Not required for the app to function**: unlike `AUTH0_DOMAIN`/
`AUTH0_AUDIENCE` (every `/api/...` call 401s without them), analytics is
optional end to end. Leaving the Measurement ID unset is a fully supported
state — `isGaConfigured` is `false`, `initAnalytics()` no-ops, and
`gtag.js` is never injected into the page at all. This is the default in
local dev (unless you opt in — see below) and in tests.

## Step 1: Create a GA4 property

**Skip this if you already have one you want to reuse.** Otherwise, sign
up at [analytics.google.com](https://analytics.google.com) and create a
property (e.g. `equiCast`), then add a **Web** data stream for your
deployed domain (Admin → Data Streams → Add stream → Web).

The stream's **Measurement ID** (shown on the stream's own detail page,
shaped like `G-XXXXXXXXXX`) is what becomes `GA_MEASUREMENT_ID`/
`VITE_GA_MEASUREMENT_ID` below — the only value this integration needs.
Unlike Auth0's Domain/Audience/Client ID split (a tenant, an API, and an
Application, each with their own identifier), GA4 has just this one ID,
since there's no separate "backend verifies, frontend logs in" split here
— the frontend is GA's only caller.

## Step 2: Wire the value into the repo

### GitHub repo variables, not secrets

Settings → Secrets and variables → Actions → **Variables** tab (same tier
`AUTH0_DOMAIN`/`AUTH0_CLIENT_ID` use — not the **Secrets** tab):

- **`GA_MEASUREMENT_ID`** = the Measurement ID from Step 1, e.g.
  `G-XXXXXXXXXX`

Not sensitive: a GA4 Measurement ID is visible in every page's rendered
HTML/network requests once analytics is loaded, by design — there's no
Client Secret equivalent here, same as Auth0's `AUTH0_CLIENT_ID` is safe to
expose (see [auth0-setup.md](auth0-setup.md)).

Following the `AUTH0_CLIENT_ID` pattern — a GitHub repo variable with no
`VITE_` prefix, mapped to `VITE_AUTH0_CLIENT_ID` only for the frontend
build by `deploy.yml`'s `deploy-frontend-dev`/`-prod` steps — this repo
variable is named **`GA_MEASUREMENT_ID`**, not `VITE_GA_MEASUREMENT_ID`;
the `VITE_` prefix only applies to the actual env var Vite reads (Step 3
below and inside the build). **No CI wiring exists for this yet** — unlike
`AUTH0_CLIENT_ID`, `deploy.yml` doesn't currently map `GA_MEASUREMENT_ID`
to `VITE_GA_MEASUREMENT_ID` for either deploy-frontend job. Add that
mapping (mirroring the three `VITE_AUTH0_*` lines in each job) if/when this
goes to production.

### Local development

Copy `frontend/.env.example` to `frontend/.env.local` (gitignored) and set:

```
VITE_GA_MEASUREMENT_ID=G-XXXXXXXXXX
```

Without it, `RequireAuth`/the rest of the app work exactly as before —
there's no "not configured" message like Auth0's, since analytics is
silently optional rather than a gating requirement.

Alternatively, [scripts/local-dev.ps1](../scripts/local-dev.ps1) supports
`-GaMeasurementId <id>` (or `$env:GA_MEASUREMENT_ID` set beforehand),
mirroring `-Auth0ClientId`'s env-var-over-`.env.local` precedence — pass it
alongside `-StartFrontend` and the spawned `npm run dev` process picks up
`VITE_GA_MEASUREMENT_ID` with no file needed. Unlike the Auth0 flags,
omitting it prints no warning — GA staying off locally is expected, not a
misconfiguration.

## Local development against localhost:5173

GA4 doesn't restrict events by hostname (unlike Universal Analytics' old
referrer checks), so the same data stream/Measurement ID from Step 1 works
unchanged against `npm run dev`'s `localhost:5173` — no separate
"localhost" stream needed. Two things to know when testing locally:

- **`localhost` traffic won't reliably show in Realtime.** GA4 filters out
  some internal/localhost-looking traffic in its default Realtime view.
  Use **Admin → DebugView** instead while developing — it shows events as
  they fire, including from `localhost`, with full per-event parameter
  detail (useful for confirming `trackEvent`'s `params` payload, not just
  that an event fired at all).
- **DebugView needs `debug_mode`.** Either install the
  [Google Analytics Debugger](https://chromewebstore.google.com/detail/google-analytics-debugger/jnkmfdileelhofjcijamephohjechhna)
  browser extension, or temporarily pass `{ debug_mode: true }` in
  `analytics.js`'s `window.gtag("config", ...)` call while testing, then
  revert before committing — don't ship `debug_mode: true`, since it also
  changes how GA buckets the traffic.

With `VITE_GA_MEASUREMENT_ID` set (Step 2) and the Analytics cookie
category accepted, `npm run dev` (or `.\scripts\local-dev.ps1
-StartFrontend -GaMeasurementId G-XXXXXXXXXX`) → visit
`http://localhost:5173` → interact with the app → events should appear in
DebugView within a few seconds.

## What gets tracked

Every automatic pageview GA4 would normally fire is disabled
(`send_page_view: false` in `ensureScriptLoaded()`) since it assumes full
page loads, which an SPA never does past the first one. Instead:

- **`page_view`** — fired by `App.jsx` on every client-side route change
  (`trackPageview`), not just the initial load.
- **`login`** — `Auth0ProviderWithNavigate.jsx`'s `onRedirectCallback`,
  firing only on a real interactive sign-in, never on a session restored
  from cache.
- **`search`** — `SearchPage.jsx`.
- **`account_created`** — `AccountsListPage.jsx`/`DashboardPage.jsx`, both
  places an account can be created.
- **`pie_created`** — `CreatePortfolioDrawer.jsx`.
- **`transaction_recorded`** — `HoldingTickerPage.jsx`'s
  `handleCreateTransaction`, covering BUY/SELL/DIVIDEND alike.

None of these carry account/holding identifiers or other personal
financial data — see the Cookie Policy page's Analytics section for the
plain-language version of this same list.

## Verifying it end-to-end

1. Set `VITE_GA_MEASUREMENT_ID`, run the frontend, and accept the
   "Analytics" cookie category (Cookie Policy page's "Manage your cookie
   preferences" button, or the banner's "Accept all").
2. Open GA4's **Admin → DebugView** (or **Reports → Realtime** for a
   deployed, non-localhost domain) and navigate around the app — a
   `page_view` should appear within a few seconds, followed by whichever
   of the events above you trigger (signing in, searching, creating an
   account/pie, recording a transaction).
3. Reject/turn off the Analytics category in preferences and confirm
   events stop appearing for that session — `syncWithConsent()` flips GA's
   own `ga-disable-<id>` opt-out flag live (no reload needed), rather than
   removing the injected `<script>` tag.
4. Turn Analytics back on and confirm events resume without a page
   refresh — `ensureScriptLoaded()` is idempotent (`scriptLoaded` guard),
   so re-enabling doesn't re-inject `gtag.js`.

## Troubleshooting

**Nothing shows in DebugView/Realtime** — check `VITE_GA_MEASUREMENT_ID`
is actually set at build/dev-server-start time (Vite bakes it in; a
`.env.local` change needs a dev server restart) and that the Analytics
cookie category is on (`hasAnalyticsConsent()` in `cookieConsent.js` —
check `localStorage`'s `ec-cookie-consent` key directly if unsure).

**Events show in Realtime but never in DebugView, or vice versa** — these
are two different GA4 views with different filtering; DebugView only shows
sessions with `debug_mode: true`, Realtime shows everything but can lag or
suppress localhost-looking traffic. Prefer DebugView while developing (see
above).

**Toggling Analytics off doesn't stop events** — check nothing else in the
codebase calls `window.gtag` directly instead of going through
`trackEvent`/`trackPageview`, which are the only two call sites gated by
`canTrack()`'s `hasAnalyticsConsent()` check.

**GA loaded once, then consent is rejected, then re-accepted, but no new
events fire** — check `listenerAttached`'s `CONSENT_CHANGED_EVENT`
listener is still attached; it's only ever added once per page load
(`initAnalytics()`'s own guard), so this would only break if
`initAnalytics()` itself isn't being called from `App.jsx` on startup.

**A GA4 Measurement ID configured but `isGaConfigured` is `false`** — the
env var name must be exactly `VITE_GA_MEASUREMENT_ID` (Vite only exposes
`VITE_`-prefixed vars to client code); a bare `GA_MEASUREMENT_ID` set in
the shell or `.env.local` is invisible to `import.meta.env`.
