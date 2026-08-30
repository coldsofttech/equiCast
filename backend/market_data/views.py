from django.conf import settings
from equicast_core import MarketDataClient
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

ASSET_CLASSES = {"fx", "stock", "etf"}

#: One shared client for the process — cheap to construct, but no reason to
#: rebuild it (and its boto3 client) on every request.
_client = MarketDataClient(settings.MARKET_DATA_BUCKET)


class ProfileView(APIView):
    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        profile = _client.get_profile(asset_class, symbol)
        if profile is None:
            return Response({"detail": f"No data for {asset_class}={symbol.upper()}."}, status=404)
        return Response(profile)


class PricesView(APIView):
    def get(self, request: Request, asset_class: str, symbol: str) -> Response:
        if asset_class not in ASSET_CLASSES:
            return Response({"detail": f"Unknown asset class '{asset_class}'."}, status=400)

        records = _client.get_prices(asset_class, symbol)
        return Response({"ticker": symbol.upper(), "results": records})
