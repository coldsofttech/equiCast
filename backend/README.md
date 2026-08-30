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

- `GET /health/` — no dependencies, used to validate the Lambda packaging
- `GET /api/market/<asset_class>/<symbol>/profile/` — `asset_class` is one of `fx`/`stock`/`etf`
- `GET /api/market/<asset_class>/<symbol>/prices/` — current calendar year only

## Lambda packaging

```bash
bash scripts/build_lambda_package.sh
```

Builds the zip deployment package this app would ship to Lambda and reports
its size against Lambda's 250MB (unzipped) deployment package limit.
