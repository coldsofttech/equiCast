# Auth0 setup

How the backend identifies API callers: Auth0 issues RS256 access tokens,
and `backend/identity/authentication.py`'s `Auth0JWTAuthentication` verifies
them against Auth0's public JWKS on every request. This is the reference for
creating the tenant/API and wiring its values into the repo; there's no
`terraform.yml` equivalent for Auth0 itself (see below).

## Why Auth0, and why one shared tenant/API

Auth0 handles the actual login flow (and, eventually, social/passwordless
providers) so the backend never touches passwords — it only ever verifies a
token someone else issued. One tenant with one API (audience), shared by
both `dev` and `prod`, rather than a tenant/API pair per environment like
`MARKET_DATA_BUCKET_DEV`/`PROD`: there's no per-environment user base to
isolate yet, and running two tenants would mean logging in twice to test
dev vs. prod. Revisit this split if/when dev and prod need genuinely
separate user pools.

**Not Terraform-managed**: unlike the AWS OIDC role
([docs/aws-github-oidc-setup.md](aws-github-oidc-setup.md)), there's no
Terraform provider wired up for Auth0 in this repo — the tenant and API are
created once, manually, in the Auth0 dashboard, and only their *values*
(`AUTH0_DOMAIN`, `AUTH0_AUDIENCE`) flow into Terraform as plain input
variables.

## Step 1: Create the Auth0 tenant

**Skip this if you already have one you want to reuse.** Otherwise, sign up
at [auth0.com](https://auth0.com) and create a tenant (e.g. `equicast`,
region `eu`) — the free tier is enough for this phase (verifying tokens
issued to a small number of users).

## Step 2: Register the API

Dashboard → **Applications → APIs → Create API**:

- **Name**: `equiCast API` (display only, doesn't affect tokens)
- **Identifier**: a URI that doesn't need to resolve, just be unique —
  e.g. `https://api.equicast.app`. This becomes `AUTH0_AUDIENCE` and is
  embedded in every token's `aud` claim.
- **Signing Algorithm**: **RS256** (the default, and what
  `Auth0JWTAuthentication` requires — it fetches the tenant's public keys
  from the JWKS endpoint rather than sharing a symmetric secret).

Your tenant's domain (shown throughout the dashboard, e.g.
`equicast.eu.auth0.com`) becomes `AUTH0_DOMAIN` — used both as the token
issuer (`https://<domain>/`) and to build the JWKS URL
(`https://<domain>/.well-known/jwks.json`).

A frontend Application (Single Page Application type, PKCE flow) to
actually log users in and obtain tokens against this API is a separate,
later step — out of scope for this backend-only phase, since the backend
only needs to *verify* tokens, not issue them.

## Step 3: Register the frontend Application

The step Step 2 deferred — `frontend/src/auth/`'s `@auth0/auth0-react`
integration needs its own Auth0 Application (not the API from Step 2) to
actually run the login flow. Dashboard → **Applications → Applications →
Create Application**:

- **Name**: `equiCast Web` (display only)
- **Application type**: **Single Page Application** — this is what makes
  Auth0 use the PKCE flow (no client secret; a SPA can't keep one
  confidential, unlike a server-side app)

In the new Application's **Settings** tab, set (comma-separated, no
spaces, if entering more than one):

- **Allowed Callback URLs**: `http://localhost:5173` for local dev, plus
  each deployed environment's CloudFront URL (`terraform output
  frontend_url` — see [terraform-state-setup.md](terraform-state-setup.md))
  once one exists
- **Allowed Logout URLs**: the same list — `Auth0ProviderWithNavigate`
  passes `returnTo: window.location.origin` to `logout()`, i.e. back to
  wherever the app is running
- **Allowed Web Origins**: the same list again — needed for Auth0's
  silent-auth (`getAccessTokenSilently`) iframe checks and doubles as
  Auth0's CORS allowlist for this Application

Only `http://localhost:5173` needs setting by hand here. Each deployed
environment's CloudFront URL is added/removed automatically from here on
— by `terraform.yml`'s `apply-dev`/`apply-prod` (via the shared
`.github/actions/terraform-apply` composite action, covering both the
first-ever apply for a new environment and every routine one after) and
by `infra-lifecycle.yml`'s destroy/redeploy jobs — see Step 3.5 below —
since that URL is reassigned by AWS every time the distribution is
recreated and would otherwise need the same manual edit repeated by hand
each time.

The **Client ID** on this same Settings tab becomes `AUTH0_CLIENT_ID`
below — unlike `AUTH0_DOMAIN`/`AUTH0_AUDIENCE`, this one has no backend
equivalent (the backend never authenticates *as* a client, only verifies
tokens someone else obtained), but it's not sensitive either: an SPA's
client ID is visible in every browser network request it makes, by
design — PKCE is exactly what makes a public client ID safe to ship.

Also authorize this Application against the Step 2 API: Dashboard →
**Applications → APIs → equiCast API → Application Access** tab, find
`equiCast Web`'s row, click **Edit**, and on the **User-Delegated Access**
sub-tab click **Grant Access** (this tenant's API has "Per-app
authorization" as its access policy — Application Access tab's banner —
so every application needs an explicit grant here before it can request
tokens for this API, even via the ordinary login/PKCE flow, not just
client-credentials). Skipping it makes `loginWithRedirect`'s `audience`
param fail with `invalid_request: Client "..." is not authorized to
access resource server "https://api.equicast.app"`, surfaced by the
frontend as a generic "Something went wrong signing in" (see
`RequireAuth.jsx`). Note this tab may be named differently ("Machine to
Machine Applications") on older Auth0 dashboards — same underlying
concept either way: an explicit per-application grant against the API.

## Step 3.5: Reuse a Machine-to-Machine Application for CI automation

A different Application from `equiCast Web` is required here — a Single
Page Application has no client secret and can't use the
`client_credentials` grant (Auth0 greys the grant type out for SPAs:
*"To use the Client Credentials grant you have to set a Token Endpoint
Auth Method other than 'none'"*), which is what
`.github/scripts/auth0_sync_redirect_uris.sh` needs to call the **Auth0
Management API** (a different, built-in API from the `equiCast API` in
Step 2 — this is what lets `infra-lifecycle.yml`'s destroy/redeploy jobs
edit `equiCast Web`'s own Allowed Callback/Logout/Web-Origin URLs,
described in Step 3 above).

This tenant already has a Machine-to-Machine Application named
**GitHub Auth0 Deployment Manager**, already authorized against the
**Auth0 Management API** with `read:clients`/`update:clients` (among
other scopes) granted — reuse it rather than creating a new one. Its
**Client ID** and **Client Secret** (Dashboard → **Applications →
Applications → GitHub Auth0 Deployment Manager → Settings**) become
`AUTH0_MGMT_CLIENT_ID`/`AUTH0_MGMT_CLIENT_SECRET` below — unlike
`equiCast Web`'s client ID, the secret here is a real bearer credential
(it's what lets `oauth/token` mint a Management API access token) and
must go in GitHub **Secrets**, not Variables.

Note this Application is scoped far more broadly than
`auth0_sync_redirect_uris.sh` needs (it holds most Management API
scopes, not just `read:clients`/`update:clients`) — accepted here to
reuse existing tenant setup rather than create a narrower one, but worth
tightening (or replacing with a dedicated, minimally-scoped Application)
if this credential's blast radius ever becomes a concern.

If `equiCast Web` (the SPA) was ever granted Management API scopes by
mistake while investigating this, they're inert (a SPA can't use them to
get a token) and can be left as-is or revoked — either way, they have no
effect on this automation.

## Step 4: Wire the values into the repo

### GitHub repo variables, not secrets

Settings → Secrets and variables → Actions → **Variables** tab (same tier
`AWS_REGION` uses — not the **Secrets** tab `AWS_ROLE_ARN` uses):

- **`AUTH0_DOMAIN`** = your tenant domain, e.g. `equicast.eu.auth0.com`
- **`AUTH0_AUDIENCE`** = the API Identifier from Step 2, e.g.
  `https://api.equicast.app`
- **`AUTH0_CLIENT_ID`** = the frontend Application's Client ID from Step 3
  — read by both the frontend build (`deploy.yml`'s
  `deploy-frontend-dev`/`-prod` map it to `VITE_AUTH0_CLIENT_ID`) and
  `infra-lifecycle.yml`'s Auth0 sync steps (Step 3.5), which patch this
  Application's redirect URLs; the backend has no use for it

None of these three is actually sensitive: the domain is a public
JWKS/authorization-server hostname, the audience is embedded in every
issued access token's `aud` claim, and a SPA's client ID is visible in
every request it makes (see Step 3). Verifying/obtaining tokens
introduces **no real secret** — the backend only verifies tokens against
Auth0's public JWKS, and the frontend is a public PKCE client, so there's
no Client Secret to store anywhere for either.

### GitHub repo secrets

Settings → Secrets and variables → Actions → **Secrets** tab (same tier
`AWS_ROLE_ARN` uses):

- **`AUTH0_MGMT_CLIENT_ID`** / **`AUTH0_MGMT_CLIENT_SECRET`** = the Step
  3.5 Machine-to-Machine Application's Client ID/Secret. Unlike the three
  variables above, this pair is a real credential — it mints Auth0
  Management API access tokens — which is why it's a Secret rather than
  a Variable, and why the Application it belongs to is scoped down to
  `read:clients`/`update:clients` only. `infra-lifecycle.yml`'s destroy/
  redeploy jobs are the only consumer, via
  `.github/scripts/auth0_sync_redirect_uris.sh`.

`terraform.yml`'s `plan`/`apply-dev`/`apply-prod` steps read the first two
as `vars.AUTH0_DOMAIN`/`vars.AUTH0_AUDIENCE` and pass them to Terraform as
`-var auth0_domain=... -var auth0_audience=...`, which `infra/main.tf` wires
straight into the backend Lambda's environment. `AUTH0_CLIENT_ID` is
frontend-only, read directly by `deploy.yml`, not passed through Terraform
at all.

### Local development

Export the same two values before running the backend locally (see
[local-setup.md](local-setup.md)):

```bash
export AUTH0_DOMAIN=equicast.eu.auth0.com
export AUTH0_AUDIENCE=https://api.equicast.app
```

For the frontend, copy `frontend/.env.example` to `frontend/.env.local`
(gitignored) and fill in `VITE_AUTH0_DOMAIN`/`VITE_AUTH0_CLIENT_ID`/
`VITE_AUTH0_AUDIENCE` with the same tenant domain, the Step 3 Application's
Client ID, and the same audience. Without it, `RequireAuth` shows a
"not configured" message instead of a login button — see
`frontend/src/auth/auth0Config.js`.

## Verifying it end-to-end

Get a short-lived test token without a frontend: Dashboard → **Applications
→ APIs → equiCast API → Test** tab has a ready-made `curl` snippet
(client-credentials grant against your own API) that returns an access
token signed for this exact domain/audience. Then:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/identity/me/
# {"user_id": "...", "default_currency": "GBP"}
```

A 401 here means either the token or the backend's `AUTH0_DOMAIN`/
`AUTH0_AUDIENCE` don't match — see Troubleshooting below. A 200 with a
freshly-created `default_currency: "GBP"` profile confirms the whole path:
token verified, `sub` claim extracted, DynamoDB upsert succeeded.

## Troubleshooting

Every `401` from a *rejected* token (as opposed to a missing one — see the
last entry below) returns the same generic `"Invalid or expired token."`
body on purpose: `Auth0JWTAuthentication` logs the specific PyJWT exception
server-side (`logger.warning`, visible in
`aws logs tail /aws/lambda/equicast-backend-<env> --follow` locally or via
CloudWatch) rather than returning it to the caller, since that text can
echo back claim values from the token. Check the logs for one of these:

**`Invalid audience`** — the token's `aud` claim doesn't match
`AUTH0_AUDIENCE`. Usually means the token was requested against a
different API than the one whose Identifier you configured.

**`Invalid issuer`** — the token's `iss` claim doesn't match
`https://<AUTH0_DOMAIN>/`. Check `AUTH0_DOMAIN` has no `https://` prefix or
trailing slash of its own (the code adds both).

**`Signature has expired`** — the test token from Step 2's "Test" tab is
short-lived; generate a new one.

**An unknown key ID (`kid`)** — the token was signed by a different tenant
than `AUTH0_DOMAIN` points at (e.g. a token from a personal/test tenant
used against the project's configured one), or the JWKS was rotated and
the process's cached keys are stale (`Auth0JWTAuthentication`'s
`PyJWKClient` caches for the process lifetime — restart the backend after
rotating signing keys).

**`401` with no logged warning / generic "Authentication credentials were
not provided"** — no `Authorization: Bearer <token>` header was sent at
all; `Auth0JWTAuthentication` treats a missing header as anonymous, not an
error, so this 401 comes from `IsAuthenticated` on `MeView`, not from token
validation, and nothing is logged.
