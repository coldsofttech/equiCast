import math

from django.conf import settings
from equicast_core import ASSET_CLASSES, DEFAULT_PRICE_RANGE, PRICE_RANGES, MarketDataClient
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
#: rebuild it (and its boto3 client) on every request.
_client = MarketDataClient(settings.MARKET_DATA_BUCKET, region_name=settings.AWS_REGION)


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


class PricesView(APIView):
    """`prices` is trimmed/aggregated to the requested `range` query param
    (one of PRICE_RANGES, default DEFAULT_PRICE_RANGE — see
    equicast_core.client.MarketDataClient.get_prices) server-side, not
    fetched-then-cut client-side — a long-history "max"/"10y" response
    could otherwise be several thousand daily rows, well past what's worth
    sending over this Lambda-behind-API-Gateway deployment (see
    backend/README.md) or rendering in a chart."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        price_range = request.query_params.get("range", DEFAULT_PRICE_RANGE)
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
        if len(query) < 1:
            return Response({"detail": "q must be at least 1 character."}, status=400)

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

        asset_classes = [asset_class] if asset_class is not None else None
        matches = _client.search(query, asset_classes=asset_classes)

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
