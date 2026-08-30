"""DRF authentication class verifying Auth0-issued RS256 access tokens.

See docs/auth0-setup.md for how AUTH0_DOMAIN/AUTH0_AUDIENCE are obtained.
"""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

#: Fetches and caches the tenant's signing keys (cache_keys=True — PyJWKClient
#: otherwise refetches the whole JWKS on every call); constructed once per
#: process, mirroring market_data/views.py's module-level client pattern.
_jwks_client = jwt.PyJWKClient(
    f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json", cache_keys=True
)


@dataclass
class Auth0User:
    """A minimal, non-persisted stand-in for `request.user` — there's no
    `django.contrib.auth` user table involved, identity lives in Auth0."""

    user_id: str
    is_authenticated: bool = True


class Auth0JWTAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[Auth0User, dict] | None:
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            # No credentials attempted — DRF tries the next authenticator
            # (or leaves the request anonymous) rather than treating this
            # as a failure, so unauthenticated market_data endpoints are
            # unaffected by this class being registered globally.
            return None

        try:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.AUTH0_AUDIENCE,
                issuer=f"https://{settings.AUTH0_DOMAIN}/",
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationFailed(f"Invalid token: {exc}") from exc

        return Auth0User(user_id=claims["sub"]), claims

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"
