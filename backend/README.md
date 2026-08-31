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
settings above, to use `/api/accounts/...`.

- `GET /health/` — no dependencies, used to validate the Lambda packaging
- `GET /api/market/<asset_class>/<symbol>/profile/` — `asset_class` is one of `fx`/`stock`/`etf`
- `GET /api/market/<asset_class>/<symbol>/prices/` — current calendar year only
- `GET /api/identity/me/` — requires a valid Auth0-issued Bearer token;
  returns the caller's profile (`user_id`, `default_currency`), creating it
  with `default_currency: "GBP"` on first login
- `GET /api/accounts/` — requires a valid Auth0-issued Bearer token; lists
  the caller's accounts
- `POST /api/accounts/` — creates an account (`name`, `description`,
  `account_type`, `currency`); `409` once the caller has 5
- `PATCH /api/accounts/<id>/` — partially updates an account
- `DELETE /api/accounts/<id>/` — deletes an account

## Lambda packaging

```bash
bash scripts/build_lambda_package.sh
```

Builds the zip deployment package this app would ship to Lambda and reports
its size against Lambda's 250MB (unzipped) deployment package limit.
