from unittest.mock import MagicMock, patch

import jwt
from django.test import TestCase
from django.urls import reverse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from identity.authentication import Auth0JWTAuthentication, Auth0User

factory = APIRequestFactory()


class Auth0JWTAuthenticationTests(TestCase):
    def setUp(self) -> None:
        self.auth = Auth0JWTAuthentication()

    def test_returns_none_when_authorization_header_missing(self) -> None:
        request = Request(factory.get("/"))

        self.assertIsNone(self.auth.authenticate(request))

    def test_returns_none_when_scheme_is_not_bearer(self) -> None:
        request = Request(factory.get("/", HTTP_AUTHORIZATION="Basic abc123"))

        self.assertIsNone(self.auth.authenticate(request))

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_auth0_user_for_valid_token(self, mock_jwks_client, mock_decode) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}
        request = Request(factory.get("/", HTTP_AUTHORIZATION="Bearer validtoken"))

        result = self.auth.authenticate(request)

        assert result is not None
        user, claims = result
        self.assertEqual(user, Auth0User(user_id="auth0|abc123"))
        self.assertEqual(claims, {"sub": "auth0|abc123"})

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_raises_authentication_failed_for_expired_token(
        self, mock_jwks_client, mock_decode
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.side_effect = jwt.ExpiredSignatureError("expired")
        request = Request(factory.get("/", HTTP_AUTHORIZATION="Bearer expiredtoken"))

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)

    @patch("identity.authentication._jwks_client")
    def test_raises_authentication_failed_for_unknown_signing_key(self, mock_jwks_client) -> None:
        mock_jwks_client.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientError("no key")
        request = Request(factory.get("/", HTTP_AUTHORIZATION="Bearer badtoken"))

        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(request)


class MeViewTests(TestCase):
    def test_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("me"))

        self.assertEqual(response.status_code, 401)

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_profile_for_authenticated_user(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}
        mock_client.get_or_create_profile.return_value = {
            "user_id": "auth0|abc123",
            "default_currency": "GBP",
        }

        response = self.client.get(reverse("me"), HTTP_AUTHORIZATION="Bearer validtoken")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user_id": "auth0|abc123", "default_currency": "GBP"})
        mock_client.get_or_create_profile.assert_called_once_with("auth0|abc123")

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_existing_profile_unchanged(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|existing"}
        mock_client.get_or_create_profile.return_value = {
            "user_id": "auth0|existing",
            "default_currency": "EUR",
        }

        response = self.client.get(reverse("me"), HTTP_AUTHORIZATION="Bearer validtoken")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["default_currency"], "EUR")
