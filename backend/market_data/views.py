import math

from django.conf import settings
from equicast_core import ASSET_CLASSES, PRICE_RANGES, MarketDataClient
from identity.authentication import Auth0JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

#: Default/max results per page for SearchView — a fixed default rather
#: than "no cap" since search is scanned + filtered in memory on every
#: request (see MarketDataClient.search); the max keeps a caller from
#: forcing an arbitrarily large single response.
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

#: One shared client for the process — cheap to construct, but no reason to
#: rebuild it (and its boto3 client) on every request. Also the instance
#: `lambda_handler.py` calls `warm_fx_cache()` on at Lambda cold start —
#: harmless that it's this module's own client rather than a dedicated
#: one, since `_read_parquet`'s cache is shared process-wide (see
#: equicast_core.client), not per-instance.
_client = MarketDataClient(
    settings.MARKET_DATA_BUCKET,
    region_name=settings.AWS_REGION,
    cache_ttl_seconds=settings.MARKET_DATA_CACHE_TTL_SECONDS,
)


def _parse_market_cap(raw: str | None) -> float | None:
    """`None` when unset, else a float — raises `ValueError` (caught by the
    caller) for anything else, same "let int()/float() do the validation"
    approach `SearchView.get` already takes for `page`/`page_size`."""
    if raw is None:
        return None
    return float(raw)


class ProfileView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        profile = _client.get_profile(asset_class, symbol)
        if profile is None:
            return Response({"detail": f"No data for {asset_class}={symbol.upper()}."}, status=404)
        return Response(profile)


class MetricsView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        metrics = _client.get_metrics(asset_class, symbol)
        if metrics is None:
            return Response({"detail": f"No data for {asset_class}={symbol.upper()}."}, status=404)
        return Response(metrics)


class DividendsView(APIView):
    """`dividends` combines every dividend record equicast_core.
    MarketDataClient.get_dividends knows about (already-paid history/
    current-year payouts, a real yfinance-declared upcoming one, and
    computed future projections) into one chronological, status-tagged
    list — see that method's docstring for the full shape. Unfiltered by
    date and not deduplicated; a caller wanting only upcoming payouts (or
    to prefer a declared one over an overlapping estimate) does that
    itself, same division of responsibility as PricesView's explicit-`range`
    path leaving range selection to the caller."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        dividends = _client.get_dividends(asset_class, symbol)
        if dividends is None:
            return Response({"detail": f"No data for {asset_class}={symbol.upper()}."}, status=404)
        return Response(dividends)


class EventsView(APIView):
    """`events` combines every corporate event equicast_core.
    MarketDataClient.get_events knows about — earnings reports, analyst
    rating changes, stock splits — into one chronological, `event_type`-
    tagged list — see that method's docstring for the full shape.
    Unfiltered by date, same division of responsibility as
    DividendsView/PricesView leaving range selection to the caller."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        events = _client.get_events(asset_class, symbol)
        if events is None:
            return Response({"detail": f"No data for {asset_class}={symbol.upper()}."}, status=404)
        return Response(events)


class PricesView(APIView):
    """Two shapes, depending on whether `range` is given:

    - No `range` query param (the frontend's own price chart — see
      HoldingPriceChart.jsx/PiePriceChart.jsx — never sends one): returns
      `equicast_core.client.MarketDataClient.get_price_history`'s bundled
      `{ticker, currency, last_updated, daily, weekly, monthly}`, fetched
      once per ticker and sliced client-side for whichever range the user
      picks, with no further request on a range change (GitHub issue #150).
    - An explicit `range` query param (one of PRICE_RANGES, for a caller
      hitting this endpoint directly rather than through the chart):
      unchanged from before — `prices` trimmed/aggregated to that one range
      server-side via `get_prices`, not fetched-then-cut client-side, since
      a long-history "max"/"10y" single-range response could otherwise be
      several thousand daily rows, well past what's worth sending over this
      Lambda-behind-API-Gateway deployment (see backend/README.md) or
      rendering in a chart. `get_price_history`'s bundled response stays a
      few hundred rows total regardless, since only its `daily` segment is
      unaggregated and that's capped at ~a year."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        if "range" not in request.query_params:
            return Response(_client.get_price_history(asset_class, symbol))

        price_range = request.query_params["range"]
        if price_range not in PRICE_RANGES:
            detail = f"Unknown range '{price_range}'. Must be one of: {', '.join(PRICE_RANGES)}."
            return Response({"detail": detail}, status=400)

        prices = _client.get_prices(asset_class, symbol, price_range=price_range)
        return Response(prices)


class SearchView(APIView):
    """Ticker/name search across every asset class's published catalog
    (see `equicast_core.catalog`) — not a live scan of the bucket, so
    result freshness matches the ingestion pipelines' own cadence, same as
    ProfileView/PricesView."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "")

        asset_class = request.query_params.get("asset_class")
        if asset_class is not None and asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        try:
            page = int(request.query_params.get("page", 1))
            page_size = int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE))
        except ValueError:
            return Response({"detail": "page/page_size must be integers."}, status=400)
        if page < 1 or page_size < 1:
            return Response({"detail": "page/page_size must be positive."}, status=400)
        page_size = min(page_size, MAX_PAGE_SIZE)

        try:
            min_market_cap = _parse_market_cap(request.query_params.get("min_market_cap"))
            max_market_cap = _parse_market_cap(request.query_params.get("max_market_cap"))
        except ValueError:
            return Response(
                {"detail": "min_market_cap/max_market_cap must be numbers."}, status=400
            )
        if (
            min_market_cap is not None
            and max_market_cap is not None
            and min_market_cap > max_market_cap
        ):
            return Response(
                {"detail": "min_market_cap must not exceed max_market_cap."}, status=400
            )

        exchange = request.query_params.get("exchange")
        region = request.query_params.get("region")
        sector = request.query_params.get("sector")
        industry = request.query_params.get("industry")

        asset_classes = [asset_class] if asset_class is not None else None
        matches = _client.search(
            query,
            asset_classes=asset_classes,
            min_market_cap=min_market_cap,
            max_market_cap=max_market_cap,
            exchange=exchange,
            region=region,
            sector=sector,
            industry=industry,
        )

        count = len(matches)
        start = (page - 1) * page_size
        results = matches[start : start + page_size]

        return Response(
            {
                "count": count,
                "page": page,
                "page_size": page_size,
                "total_pages": math.ceil(count / page_size) if count else 0,
                "results": results,
            }
        )
