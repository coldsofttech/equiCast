import math

from django.conf import settings
from equicast_core import ASSET_CLASSES, PRICE_RANGES, MarketDataClient
from identity.authentication import Auth0JWTAuthentication
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

#: Default/max results per page for SearchView — a fixed default rather
#: than "no cap" since search is scanned + filtered in memory on every
#: request (see MarketDataClient.search); the max keeps a caller from
#: forcing an arbitrarily large single response.
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200

#: The landing page's pre-login demo chart (PublicDemoPricesView) — a
#: fixed, small allowlist rather than an arbitrary ticker, since this is
#: the one market_data endpoint with no IsAuthenticated at all (see that
#: view's docstring). (asset_class, ticker) order here is also the
#: response order.
DEMO_TICKERS = [("stock", "AAPL"), ("stock", "NVDA"), ("etf", "VOO")]

#: Max `items` a BulkProfileView/BulkMetricsView request can carry — these
#: exist to replace a page's N individual GET .../profile/ or .../metrics/
#: calls (one per holding) with a single request (GitHub issue #203), but a
#: caller could otherwise send an arbitrarily large `items` list in one
#: request; this caps it at well beyond any real account/pie's holding
#: count, same "reasonable ceiling, not a real limit" role MAX_PAGE_SIZE
#: plays for SearchView.
MAX_BULK_ITEMS = 200

#: BulkPricesView's own, much lower ceiling than MAX_BULK_ITEMS above.
#: Unlike a profile/metrics record (a handful of scalar fields), a price
#: item is get_price_history's full {daily, weekly, monthly} bundle — for a
#: ~20-year-old holding that's on the order of 45-65KB of JSON per item, so
#: MAX_BULK_ITEMS worth of them in one response could approach API Gateway/
#: Lambda's 10MB response cap. 100 keeps a full page comfortably under that
#: even for a page of all long-history (~40yr) holdings (~6.5MB worst case)
#: while still collapsing a large account's holdings into a small, fixed
#: number of requests (frontend api/market.js's getBulkPrices chunks into
#: pages of this size and calls this endpoint once per page).
MAX_BULK_PRICE_ITEMS = 100

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


def _validate_bulk_items(
    data: object, max_items: int = MAX_BULK_ITEMS
) -> list[dict[str, str]] | Response:
    """Shared request-body validation for BulkProfileView/BulkMetricsView/
    BulkPricesView — all three expect `{"items": [{"asset_class": str,
    "symbol": str}, ...]}`. Returns the validated `items` list, or a
    ready-to-return 400 `Response` describing what's wrong. An unknown
    `asset_class` on an individual item is deliberately *not* validated
    here — that's a per-item "no data" case each view resolves to `None`
    for, same as an unpublished symbol, rather than failing the whole batch
    for one bad entry (a caller mixing a typo'd item among otherwise-valid
    ones still gets the rest back). `max_items` defaults to MAX_BULK_ITEMS;
    BulkPricesView passes its own, much lower MAX_BULK_PRICE_ITEMS (see
    that constant's docstring)."""
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return Response(
            {"detail": 'Expected a JSON body: {"items": [{"asset_class", "symbol"}, ...]}.'},
            status=400,
        )

    items = data["items"]
    if not items:
        return Response({"detail": "items must not be empty."}, status=400)
    if len(items) > max_items:
        return Response({"detail": f"items must not exceed {max_items}."}, status=400)

    for item in items:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("asset_class"), str)
            or not isinstance(item.get("symbol"), str)
        ):
            return Response(
                {"detail": 'Each item must be {"asset_class": str, "symbol": str}.'}, status=400
            )

    return items


class BulkProfileView(APIView):
    """POST counterpart to ProfileView — takes a list of `{asset_class,
    symbol}` items and returns one profile (or `None`) per item, in the
    same order, so a page listing N holdings (an account/pie's own, or a
    portfolio rating's underlying instruments — see frontend api/market.js's
    getBulkProfiles) can fetch every holding's profile in one request
    instead of N (GitHub issue #203). Each item's data still comes from
    `MarketDataClient.get_profile`, so it's cached exactly as it would be
    for an individual GET .../profile/ call (see that client's
    `_read_parquet` docstring) — this endpoint only collapses the HTTP
    round trips, not the underlying per-symbol cache."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        items = _validate_bulk_items(request.data)
        if isinstance(items, Response):
            return items

        results = []
        for item in items:
            asset_class = item["asset_class"]
            symbol = item["symbol"]
            profile = (
                _client.get_profile(asset_class, symbol) if asset_class in ASSET_CLASSES else None
            )
            results.append({"asset_class": asset_class, "symbol": symbol, "profile": profile})
        return Response({"results": results})


class BulkMetricsView(APIView):
    """POST counterpart to MetricsView — see BulkProfileView's docstring,
    identical shape/behavior with `metrics`/`MarketDataClient.get_metrics`
    in place of `profile`/`get_profile`."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        items = _validate_bulk_items(request.data)
        if isinstance(items, Response):
            return items

        results = []
        for item in items:
            asset_class = item["asset_class"]
            symbol = item["symbol"]
            metrics = (
                _client.get_metrics(asset_class, symbol) if asset_class in ASSET_CLASSES else None
            )
            results.append({"asset_class": asset_class, "symbol": symbol, "metrics": metrics})
        return Response({"results": results})


class BulkPricesView(APIView):
    """POST counterpart to PricesView's no-`range` shape — see
    BulkProfileView's docstring, identical shape/behavior with `prices`/
    `MarketDataClient.get_price_history` in place of `profile`/
    `get_profile`, except capped at MAX_BULK_PRICE_ITEMS rather than
    MAX_BULK_ITEMS (see that constant's docstring for why). Exists for the
    same reason as BulkProfileView/BulkMetricsView: a page charting N
    holdings' price history at once (an account's direct + pie-nested
    holdings, or a pie's own — see frontend pies/PiePriceChart.jsx's
    fetchHoldingHistories) was firing N individual GET .../prices/ calls in
    parallel, enough to trip the per-user request-rate throttle
    (identity.throttling.Auth0UserRateThrottle) once a portfolio has more
    than a handful of holdings. The frontend (api/market.js's
    getBulkPrices) chunks a large holdings list into MAX_BULK_PRICE_ITEMS-
    sized pages and calls this endpoint once per page, sequentially."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        items = _validate_bulk_items(request.data, max_items=MAX_BULK_PRICE_ITEMS)
        if isinstance(items, Response):
            return items

        results = []
        for item in items:
            asset_class = item["asset_class"]
            symbol = item["symbol"]
            prices = (
                _client.get_price_history(asset_class, symbol)
                if asset_class in ASSET_CLASSES
                else None
            )
            results.append({"asset_class": asset_class, "symbol": symbol, "prices": prices})
        return Response({"results": results})


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


class NewsView(APIView):
    """`news` is every article published in the trailing month for this
    ticker/pair, newest first (see
    `equicast_core.client.MarketDataClient.get_news`). Not published for
    every asset class - fx tickers have no `news.parquet` at all (the fx
    ingestion pipeline never writes one), so this 404s the same as any
    other unpublished ticker rather than needing a separate asset-class
    check here."""

    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        news = _client.get_news(asset_class, symbol)
        if news is None:
            return Response({"detail": f"No data for {asset_class}={symbol.upper()}."}, status=404)
        return Response(news)


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

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        rate = _client.get_fx_rate_on_date(from_currency, to_currency, date)
        if rate is None:
            return Response(
                {"detail": f"No FX rate for {from_currency}/{to_currency} on or before {date}."},
                status=404,
            )
        return Response(
            {"from_currency": from_currency, "to_currency": to_currency, "date": date, "rate": rate}
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


class PublicDemoRateThrottle(AnonRateThrottle):
    """A dedicated, IP-keyed scope (`"public_demo"` — rate set via
    `DEFAULT_THROTTLE_RATES` in settings.py) for `PublicDemoPricesView`,
    the one market_data endpoint with no `IsAuthenticated` at all. Every
    other endpoint here is protected by `Auth0UserRateThrottle`'s
    per-caller "user" scope, which needs a real identity; this one has
    none to key off, so DRF's own IP-keyed `AnonRateThrottle` is the right
    base instead of that class's rarely-exercised anonymous fallback."""

    scope = "public_demo"


class PublicDemoPricesView(APIView):
    """GET, no auth — the pre-login landing page's demo chart (SignInScreen/
    DemoChart.jsx) needs real price data before a visitor has signed in,
    which every other market_data endpoint can't serve (all require
    `IsAuthenticated`). Deliberately narrow rather than opening up
    ProfileView/PricesView themselves: only ever serves `DEMO_TICKERS` (a
    fixed, hardcoded allowlist — AAPL, NVDA, VOO), so this can't become a
    way to scrape the full catalog unauthenticated. `PublicDemoRateThrottle`
    (IP-keyed, not per-user) guards against that same risk from the demand
    side."""

    authentication_classes: list[type[BaseAuthentication]] = []
    permission_classes = [AllowAny]
    throttle_classes = [PublicDemoRateThrottle]

    def get(self, request: Request) -> Response:
        tickers = []
        for asset_class, symbol in DEMO_TICKERS:
            profile = _client.get_profile(asset_class, symbol)
            prices = _client.get_prices(asset_class, symbol, price_range="1m")
            tickers.append(
                {
                    "ticker": symbol,
                    "asset_class": asset_class,
                    "name": profile.get("name") if profile else symbol,
                    "currency": prices.get("currency"),
                    "prices": prices.get("prices", []),
                }
            )
        return Response({"tickers": tickers})
