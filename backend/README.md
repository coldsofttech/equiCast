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
settings above, to use
`/api/accounts/...`/`/api/pies/...`/`/api/watchlists/...`/`/api/holdings/...`/`/api/transactions/...`.

Set `MAX_ACCOUNTS`/`MAX_PIES`/`MAX_WATCHLISTS` (defaults `5`/`20`/`5`) to tune
the accounts-per-user, pies-per-account, and watchlists-per-user caps without
a code change — see `infra/variables.tf`'s `max_accounts`/`max_pies`/
`max_watchlists`, set per-environment via the `development`/`production`
GitHub Environments' `MAX_ACCOUNTS`/`MAX_PIES`/`MAX_WATCHLISTS` variables.
Set `MAX_HOLDINGS_FOR_ACCOUNT`/`MAX_HOLDINGS_FOR_PIE`/
`MAX_HOLDINGS_FOR_WATCHLIST` (defaults `100`/`50`/`20`) the same way to tune
the holdings-per-account/pie/watchlist caps — see `infra/variables.tf`'s
`max_holdings_for_account`/`max_holdings_for_pie`/`max_holdings_for_watchlist`.
Set `MAX_TRANSACTIONS_FOR_HOLDING` (default `500`) the same way to tune the
transactions-per-holding cap — see `infra/variables.tf`'s
`max_transactions_for_holding`.

- `GET /health/` — no dependencies, used to validate the Lambda packaging
- `GET /api/market/<asset_class>/<symbol>/profile/` — `asset_class` is one of `fx`/`stock`/`etf`
- `GET /api/market/<asset_class>/<symbol>/prices/` — current calendar year only
- `GET /api/market/search/` — ticker/name search; `?q=` required (at least 1
  character), case-insensitive substring match against every published
  catalog's `ticker`/`name` (see `equicast_core.catalog`), so results are
  only as fresh as the last ingestion run — not a live bucket scan. Optional
  `?asset_class=` narrows to one of `fx`/`stock`/`etf`. Paginated
  (`?page=`, default `1`; `?page_size=`, default `50`, capped at `200`),
  returning `{count, page, page_size, total_pages, results}`
- `GET /api/identity/me/` — requires a valid Auth0-issued Bearer token;
  returns the caller's profile (`user_id`, `default_currency`), creating it
  with `default_currency: "GBP"` on first login
- `GET /api/accounts/` — requires a valid Auth0-issued Bearer token; lists
  the caller's accounts
- `POST /api/accounts/` — creates an account (`name`, `description`,
  `account_type`, `currency`, `transaction_type` — `AVERAGE` or
  `TRANSACTION`); `409` once the caller has `MAX_ACCOUNTS`
- `GET /api/accounts/<id>/` — an account's details plus its nested `pies`
  (each with its own nested `holdings`) and the account's own direct
  `holdings`
- `PATCH /api/accounts/<id>/` — partially updates an account;
  `transaction_type` is rejected with `409` once the account has any
  transactions recorded under it (directly, or via one of its pies)
- `DELETE /api/accounts/<id>/` — deletes an account; `409` if it still has
  pies and/or direct holdings — pass `?force=true` to delete those along
  with the account
- `GET /api/pies/` — lists the caller's pies; optional `?account_id=` filter
- `POST /api/pies/` — creates a pie under `account_id` (`name`,
  `description`, `account_id`); `400` if `account_id` isn't one of the
  caller's own accounts; `409` once that account has `MAX_PIES`
- `GET /api/pies/<id>/` — a pie's details plus its nested `holdings`
- `PATCH /api/pies/<id>/` — partially updates a pie's `name`/`description`
  (`account_id` is immutable)
- `DELETE /api/pies/<id>/` — deletes a pie; `409` if it still has holdings —
  pass `?force=true` to delete those holdings along with the pie
- `PUT /api/pies/<id>/holdings/` — the only way to add/remove/reallocate a
  pie's holdings, since a standalone single-item write can't keep a pie's
  allocations summing to exactly 100%; body is
  `{"add": [{"ticker", "asset_class", "allocation_pct"}, ...], "remove":
  [holding_id, ...], "reallocate": [{"id", "allocation_pct"}, ...]}`
  (each key optional). Validated atomically — every `add` ticker must have
  market data and not already be held in the pie, every `remove`/
  `reallocate` id must belong to the pie, and the resulting holdings (once
  non-empty) must sum to exactly 100%; any failure writes nothing.
- `GET /api/watchlists/` — lists the caller's watchlists (user-level, not
  nested under an account)
- `POST /api/watchlists/` — creates a watchlist (`name`, `description`);
  `409` once the caller has `MAX_WATCHLISTS`
- `GET /api/watchlists/<id>/` — a watchlist's details plus its nested
  `holdings`
- `PATCH /api/watchlists/<id>/` — partially updates a watchlist's
  `name`/`description`
- `DELETE /api/watchlists/<id>/` — deletes a watchlist; `409` if it still has
  holdings — pass `?force=true` to delete those holdings along with the
  watchlist
- `GET /api/holdings/` — lists the caller's holdings; at most one of
  `?account_id=`/`?pie_id=`/`?watchlist_id=` may be given
- `POST /api/holdings/` — creates a holding directly under `account_id` or
  `watchlist_id` (`ticker`, `asset_class` — one of `fx`/`stock`/`etf` —
  and exactly one of `account_id`/`watchlist_id`; pie-scoped holdings go
  through `PUT /api/pies/<id>/holdings/` instead); `400` if the ticker has
  no market data or the account/watchlist isn't the caller's own; `409` for
  a duplicate ticker in that parent or once it's at its cap
  (`MAX_HOLDINGS_FOR_ACCOUNT`/`MAX_HOLDINGS_FOR_WATCHLIST`)
  Optionally pairs the holding with its first transaction in the same
  request: a nested `"transaction"` field, shaped by the owning account's
  `transaction_type` (see below), validated before the holding is written;
  if the transaction can't be recorded, the holding it was paired with
  isn't created either (S3 has no cross-object transaction of its own, so
  this is a compensating delete rather than a real rollback)
- `GET /api/holdings/<id>/` — a holding's details
- `DELETE /api/holdings/<id>/` — deletes an account-direct or watchlist
  holding (`400` for a pie-scoped one — use the pie's batch endpoint
  instead); no `PATCH` — a holding's fields are immutable. Cascades into
  deleting the holding's own transactions
- `GET /api/transactions/` — lists the caller's transactions; optional
  `?holding_id=`, `?year=`, `?date_from=`/`?date_to=` filters (the date
  filters only ever match `TRANSACTION`-mode records — an `AVERAGE`
  record has no date). Transactions are stored one JSON object per
  holding rather than per user (see `packages/core/README.md`), so
  omitting `?holding_id=` reads every one of the caller's holding files
- `POST /api/transactions/` — records a transaction against an existing
  `holding_id`; `400` if the holding is fx or watchlist-scoped (neither
  supports transactions). Field shape depends on the holding's account's
  `transaction_type`: `AVERAGE` requires `no_of_shares`/`average_price`
  (`409` for a second record against the same holding — `PATCH` it
  instead of creating another); `TRANSACTION` requires
  `no_of_shares`/`price`/`date`/`type` (`BUY` or `SELL`; `409` if a `SELL`
  would take the holding's net recorded shares below zero, or once the
  holding is at `MAX_TRANSACTIONS_FOR_HOLDING`)
- `GET /api/transactions/<holding_id>/<id>/` — a transaction's details.
  Nested under its holding rather than a flat id, since a bare
  `transaction_id` would otherwise mean scanning every holding's file to
  find it — the caller already has `holding_id` in hand wherever a
  transaction is shown, since transactions are only ever listed scoped
  to a holding
- `PATCH /api/transactions/<holding_id>/<id>/` — updates an
  `AVERAGE`-mode record's `no_of_shares`/`average_price`; `400` for a
  `TRANSACTION`-mode record (immutable — buy/sell events are a log, not
  a snapshot)
- `DELETE /api/transactions/<holding_id>/<id>/` — deletes a transaction

## Lambda packaging

```bash
bash scripts/build_lambda_package.sh
```

Builds the zip deployment package this app would ship to Lambda and reports
its size against Lambda's 250MB (unzipped) deployment package limit.
