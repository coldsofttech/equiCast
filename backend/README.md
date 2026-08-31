# equicast-backend

Django REST API exposing equicast's market data (FX/stock/ETF profiles and
prices, read from S3 via [`equicast-core`](../packages/core/README.md)).
Deployed as a zip-based AWS Lambda function (via `mangum`) behind API
Gateway — not a container; `Dockerfile` exists for local testing only.

## Local development

```bash
uv sync --extra dev
uv run manage.py migrate
uv run manage.py runserver
```

Set `MARKET_DATA_BUCKET` (e.g. `equicast-market-data-dev`) to actually serve
data — without it, the server still starts, but every `/api/market/...`
request fails. Needs working AWS read credentials for that bucket locally.

Set `AUTH0_DOMAIN`, `AUTH0_AUDIENCE`, and `USER_PROFILES_TABLE` (e.g.
`equicast-user-profiles-dev`) to use `/api/identity/...` — see
[docs/auth0-setup.md](../docs/auth0-setup.md). Without them, the server
still starts and `/api/market/...` is unaffected, but any request with an
`Authorization: Bearer` header fails to authenticate, and
`/api/identity/me/` always returns `401`.

Set `USER_DATA_BUCKET` (e.g. `equicast-user-data-dev`), plus the same Auth0
settings above, to use `/api/accounts/...`/`/api/pies/...`/`/api/watchlists/...`.

Set `MAX_ACCOUNTS`/`MAX_PIES`/`MAX_WATCHLISTS` (defaults `5`/`20`/`5`) to tune
the accounts-per-user, pies-per-account, and watchlists-per-user caps without
a code change — see `infra/variables.tf`'s `max_accounts`/`max_pies`/
`max_watchlists`, set per-environment via the `development`/`production`
GitHub Environments' `MAX_ACCOUNTS`/`MAX_PIES`/`MAX_WATCHLISTS` variables.

- `GET /health/` — no dependencies, used to validate the Lambda packaging
- `GET /api/market/<asset_class>/<symbol>/profile/` — `asset_class` is one of `fx`/`stock`/`etf`
- `GET /api/market/<asset_class>/<symbol>/prices/` — current calendar year only
- `GET /api/identity/me/` — requires a valid Auth0-issued Bearer token;
  returns the caller's profile (`user_id`, `default_currency`), creating it
  with `default_currency: "GBP"` on first login
- `GET /api/accounts/` — requires a valid Auth0-issued Bearer token; lists
  the caller's accounts
- `POST /api/accounts/` — creates an account (`name`, `description`,
  `account_type`, `currency`); `409` once the caller has `MAX_ACCOUNTS`
- `GET /api/accounts/<id>/` — an account's details plus its nested `pies`
- `PATCH /api/accounts/<id>/` — partially updates an account
- `DELETE /api/accounts/<id>/` — deletes an account; `409` if it still has
  pies — pass `?force=true` to delete those pies along with the account
- `GET /api/pies/` — lists the caller's pies; optional `?account_id=` filter
- `POST /api/pies/` — creates a pie under `account_id` (`name`,
  `description`, `account_id`); `400` if `account_id` isn't one of the
  caller's own accounts; `409` once that account has `MAX_PIES`
- `GET /api/pies/<id>/` — a pie's details
- `PATCH /api/pies/<id>/` — partially updates a pie's `name`/`description`
  (`account_id` is immutable)
- `DELETE /api/pies/<id>/` — deletes a pie
- `GET /api/watchlists/` — lists the caller's watchlists (user-level, not
  nested under an account)
- `POST /api/watchlists/` — creates a watchlist (`name`, `description`);
  `409` once the caller has `MAX_WATCHLISTS`
- `GET /api/watchlists/<id>/` — a watchlist's details
- `PATCH /api/watchlists/<id>/` — partially updates a watchlist's
  `name`/`description`
- `DELETE /api/watchlists/<id>/` — deletes a watchlist

## Lambda packaging

```bash
bash scripts/build_lambda_package.sh
```

Builds the zip deployment package this app would ship to Lambda and reports
its size against Lambda's 250MB (unzipped) deployment package limit.
