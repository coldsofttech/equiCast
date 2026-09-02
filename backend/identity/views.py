from django.conf import settings
from equicast_core import UserProfileClient
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.authentication import Auth0JWTAuthentication

#: Mirrors the closed set the frontend's Settings picker offers (see
#: frontend/src/config/currencies.json) — kept here rather than fetched by
#: the frontend from an endpoint, so this is the one place both sides need
#: to stay in sync if the supported list ever changes.
SUPPORTED_CURRENCIES = {"GBP", "USD", "INR", "EUR"}

#: One shared client for the process, mirroring market_data/views.py's
#: module-level _client pattern.
_client = UserProfileClient(settings.USER_PROFILES_TABLE, region_name=settings.AWS_REGION)


class MeView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        profile = _client.get_or_create_profile(request.user.user_id)
        return Response(profile)

    def patch(self, request: Request) -> Response:
        if "default_currency" not in request.data:
            return Response({"detail": "Missing field: default_currency."}, status=400)

        default_currency = request.data["default_currency"]
        if default_currency not in SUPPORTED_CURRENCIES:
            return Response(
                {"detail": f"Unknown default_currency '{default_currency}'."}, status=400
            )

        profile = _client.update_default_currency(request.user.user_id, default_currency)
        return Response(profile)
