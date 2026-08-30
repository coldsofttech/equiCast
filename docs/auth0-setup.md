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

## Step 3: Wire the values into the repo

### GitHub repo variables, not secrets

Settings → Secrets and variables → Actions → **Variables** tab (same tier
`AWS_REGION` uses — not the **Secrets** tab `AWS_ROLE_ARN` uses):

- **`AUTH0_DOMAIN`** = your tenant domain, e.g. `equicast.eu.auth0.com`
- **`AUTH0_AUDIENCE`** = the API Identifier from Step 2, e.g.
  `https://api.equicast.app`

Neither value is actually sensitive: the domain is a public
JWKS/authorization-server hostname, and the audience is embedded in every
issued access token's `aud` claim (and has to be hardcoded into the
frontend's Auth0 config too, to request tokens in the first place). This
phase introduces **no real secret** — the backend only verifies tokens
against Auth0's public JWKS, it never authenticates itself to Auth0, so
there's no Client Secret to store anywhere. (A later phase calling Auth0's
Management API would need one, via `secrets.*`, not Terraform state.)

`terraform.yml`'s `plan`/`apply-dev`/`apply-prod` steps read these as
`vars.AUTH0_DOMAIN`/`vars.AUTH0_AUDIENCE` and pass them to Terraform as
`-var auth0_domain=... -var auth0_audience=...`, which `infra/main.tf` wires
straight into the backend Lambda's environment.

### Local development

Export the same two values before running the backend locally (see
[local-setup.md](local-setup.md)):

```bash
export AUTH0_DOMAIN=equicast.eu.auth0.com
export AUTH0_AUDIENCE=https://api.equicast.app
```

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
