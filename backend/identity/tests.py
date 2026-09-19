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

    def test_patch_returns_401_when_unauthenticated(self) -> None:
        response = self.client.patch(
            reverse("me"), data={"default_currency": "EUR"}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 401)

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_default_currency(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}
        mock_client.update_default_currency.return_value = {
            "user_id": "auth0|abc123",
            "default_currency": "EUR",
        }

        response = self.client.patch(
            reverse("me"),
            data={"default_currency": "EUR"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user_id": "auth0|abc123", "default_currency": "EUR"})
        mock_client.update_default_currency.assert_called_once_with("auth0|abc123", "EUR")

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_rejects_missing_default_currency(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}

        response = self.client.patch(
            reverse("me"),
            data={},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken",
        )

        self.assertEqual(response.status_code, 400)
        mock_client.update_default_currency.assert_not_called()

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_fx_warmup_currencies(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}
        mock_client.update_fx_warmup_currencies.return_value = {
            "user_id": "auth0|abc123",
            "fx_warmup_currencies": ["GBP", "INR"],
        }

        response = self.client.patch(
            reverse("me"),
            data={"fx_warmup_currencies": ["GBP", "INR"]},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"user_id": "auth0|abc123", "fx_warmup_currencies": ["GBP", "INR"]}
        )
        mock_client.update_fx_warmup_currencies.assert_called_once_with(
            "auth0|abc123", ["GBP", "INR"]
        )

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_rejects_unsupported_fx_warmup_currency(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}

        response = self.client.patch(
            reverse("me"),
            data={"fx_warmup_currencies": ["GBP", "JPY"]},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken",
        )

        self.assertEqual(response.status_code, 400)
        mock_client.update_fx_warmup_currencies.assert_not_called()

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_tax_residency(self, mock_jwks_client, mock_decode, mock_client) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}
        mock_client.update_tax_residency.return_value = {
            "user_id": "auth0|abc123",
            "tax_residency": "UK",
        }

        response = self.client.patch(
            reverse("me"),
            data={"tax_residency": "UK"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user_id": "auth0|abc123", "tax_residency": "UK"})
        mock_client.update_tax_residency.assert_called_once_with("auth0|abc123", "UK")

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_rejects_unsupported_tax_residency(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}

        response = self.client.patch(
            reverse("me"),
            data={"tax_residency": "US"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken",
        )

        self.assertEqual(response.status_code, 400)
        mock_client.update_tax_residency.assert_not_called()

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_income_tax_band(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}
        mock_client.update_income_tax_band.return_value = {
            "user_id": "auth0|abc123",
            "income_tax_band": "HIGHER",
        }

        response = self.client.patch(
            reverse("me"),
            data={"income_tax_band": "HIGHER"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"user_id": "auth0|abc123", "income_tax_band": "HIGHER"})
        mock_client.update_income_tax_band.assert_called_once_with("auth0|abc123", "HIGHER")

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_rejects_unsupported_income_tax_band(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}

        response = self.client.patch(
            reverse("me"),
            data={"income_tax_band": "EXTREME"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken",
        )

        self.assertEqual(response.status_code, 400)
        mock_client.update_income_tax_band.assert_not_called()

    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_rejects_unsupported_currency(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}

        response = self.client.patch(
            reverse("me"),
            data={"default_currency": "JPY"},
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken",
        )

        self.assertEqual(response.status_code, 400)
        mock_client.update_default_currency.assert_not_called()

    def test_delete_returns_401_when_unauthenticated(self) -> None:
        response = self.client.delete(reverse("me"))

        self.assertEqual(response.status_code, 401)

    @patch("identity.views._watchlists_client")
    @patch("identity.views._goals_client")
    @patch("identity.views._pies_client")
    @patch("identity.views._accounts_client")
    @patch("identity.views._transactions_client")
    @patch("identity.views._holdings_client")
    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_wipes_every_domain_for_the_caller(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_holdings_client,
        mock_transactions_client,
        mock_accounts_client,
        mock_pies_client,
        mock_goals_client,
        mock_watchlists_client,
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}
        mock_holdings_client.list_holdings.return_value = [{"id": "h1"}, {"id": "h2"}]

        response = self.client.delete(reverse("me"), HTTP_AUTHORIZATION="Bearer validtoken")

        self.assertEqual(response.status_code, 204)
        mock_holdings_client.list_holdings.assert_called_once_with("auth0|abc123")
        mock_transactions_client.delete_transactions_for_holdings.assert_called_once_with(
            "auth0|abc123", ["h1", "h2"]
        )
        mock_holdings_client.delete_all_holdings.assert_called_once_with("auth0|abc123")
        mock_accounts_client.delete_all_accounts.assert_called_once_with("auth0|abc123")
        mock_pies_client.delete_all_pies.assert_called_once_with("auth0|abc123")
        mock_goals_client.delete_all_goals.assert_called_once_with("auth0|abc123")
        mock_watchlists_client.delete_all_watchlists.assert_called_once_with("auth0|abc123")
        mock_client.delete_profile.assert_called_once_with("auth0|abc123")

    @patch("identity.views._watchlists_client")
    @patch("identity.views._goals_client")
    @patch("identity.views._pies_client")
    @patch("identity.views._accounts_client")
    @patch("identity.views._transactions_client")
    @patch("identity.views._holdings_client")
    @patch("identity.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_skips_transactions_cleanup_when_no_holdings(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_holdings_client,
        mock_transactions_client,
        mock_accounts_client,
        mock_pies_client,
        mock_goals_client,
        mock_watchlists_client,
    ) -> None:
        mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
        mock_decode.return_value = {"sub": "auth0|abc123"}
        mock_holdings_client.list_holdings.return_value = []

        response = self.client.delete(reverse("me"), HTTP_AUTHORIZATION="Bearer validtoken")

        self.assertEqual(response.status_code, 204)
        mock_transactions_client.delete_transactions_for_holdings.assert_not_called()
        mock_holdings_client.delete_all_holdings.assert_called_once_with("auth0|abc123")
