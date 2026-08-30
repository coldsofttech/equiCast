from django.conf import settings
from equicast_core import UserProfileClient
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from identity.authentication import Auth0JWTAuthentication

#: One shared client for the process, mirroring market_data/views.py's
#: module-level _client pattern.
_client = UserProfileClient(settings.USER_PROFILES_TABLE, region_name=settings.AWS_REGION)


class MeView(APIView):
    authentication_classes = [Auth0JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        profile = _client.get_or_create_profile(request.user.user_id)
        return Response(profile)
