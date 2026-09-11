"""Lambda entrypoint: wraps the Django ASGI app for API Gateway (HTTP API,
payload format 2.0) via `mangum`.

`lifespan="off"` is required — Django's ASGI handler doesn't implement the
lifespan protocol mangum otherwise tries to negotiate on cold start.

Also pre-warms `MarketDataClient`'s shared, process-wide parquet cache
(see `equicast_core.client`) with the fx catalog and every configured
pair's current-year prices, once per cold start. Fx conversion
(`get_fx_rate_on_date`, via `resolve_converted_amounts`) sits on the
request path of nearly every write (a transaction in a non-default
currency) and every holdings/pies/accounts read (`enrich_holdings`) — the
one piece of market data genuinely needed "for any operation" (see
`MarketDataClient.warm_fx_cache`'s own docstring), unlike a single stock/
etf/benchmark profile a given request may never touch. Deliberately done
here rather than in a Django `AppConfig.ready()` hook, so it only ever
runs for the actual deployed Lambda — this module is never imported by
`manage.py test`/local `runserver`, only by the Lambda runtime itself (as
the configured handler, `equicast_api.lambda_handler.handler` — see
`infra/main.tf`).
"""

from django.conf import settings
from equicast_core import MarketDataClient
from mangum import Mangum

from equicast_api.asgi import application

handler = Mangum(application, lifespan="off")

MarketDataClient(
    settings.MARKET_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    cache_ttl_seconds=settings.MARKET_DATA_CACHE_TTL_SECONDS,
).warm_fx_cache()
