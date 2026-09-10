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
    itself, same division of responsibility as PricesView leaving range
    selection to the caller."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        dividends = _client.get_dividends(asset_class, symbol)
        if dividends is None:
            return Response({"detail": f"No data for {asset_class}={symbol.upper()}."}, status=404)
        return Response(dividends)


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


class FxRateView(APIView):
    """The historical FX rate between two currencies on a given date —
    wraps `MarketDataClient.get_fx_rate_on_date` unchanged. Used by the
    transaction form to show/default the rate a BUY/SELL/DIVIDEND would
    otherwise auto-resolve server-side (see backend/transactions/views.py's
    `resolve_converted_amounts`), letting the user preview and override it
    before submitting, and by the frontend's login-time warm-up (GitHub
    issue #149) to pre-read the relevant currency pairs' parquet files
    into this process's cache ahead of any real transaction entry.

    Not nested under `<asset_class>/<symbol>/` like the views above —
    this is currency-pair-shaped, not ticker-shaped."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, from_currency: str, to_currency: str) -> Response:
        date = request.query_params.get("date")
        if not date:
            return Response({"detail": "Missing query param: date."}, status=400)

        rate = _client.get_fx_rate_on_date(from_currency.upper(), to_currency.upper(), date)
        if rate is None:
            return Response(
                {"detail": f"No FX rate for {from_currency.upper()}/{to_currency.upper()} on or before {date}."},
                status=404,
            )
        return Response(
            {"from_currency": from_currency.upper(), "to_currency": to_currency.upper(), "date": date, "rate": rate}
        )


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
