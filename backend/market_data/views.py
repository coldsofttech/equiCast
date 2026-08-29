from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import get_history


class TickerHistoryView(APIView):
    def get(self, request: Request, ticker: str) -> Response:
        period = request.query_params.get("period", "1y")
        interval = request.query_params.get("interval", "1d")
        records = get_history(ticker, period=period, interval=interval)
        return Response({"ticker": ticker.upper(), "results": records})
