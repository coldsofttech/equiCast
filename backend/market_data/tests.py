from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class ProfileViewTests(TestCase):
    def test_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("profile", args=["stock", "aapl"]))

        self.assertEqual(response.status_code, 401)

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_profile_for_known_symbol(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_profile.return_value = {"ticker": "AAPL", "name": "Apple Inc."}

        response = self.client.get(reverse("profile", args=["stock", "aapl"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ticker": "AAPL", "name": "Apple Inc."})
        mock_client.get_profile.assert_called_once_with("stock", "aapl")

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_404_when_symbol_not_found(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_profile.return_value = None

        response = self.client.get(reverse("profile", args=["stock", "unknown"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_for_unknown_asset_class(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(reverse("profile", args=["crypto", "btc"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 400)


class PricesViewTests(TestCase):
    def test_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("prices", args=["etf", "voo"]))

        self.assertEqual(response.status_code, 401)

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_price_records(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_prices.return_value = [{"ticker": "VOO", "date": "2026-01-02"}]

        response = self.client.get(reverse("prices", args=["etf", "voo"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "VOO")
        self.assertEqual(data["results"], [{"ticker": "VOO", "date": "2026-01-02"}])
        mock_client.get_prices.assert_called_once_with("etf", "voo")

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_empty_results_when_no_data(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_prices.return_value = []

        response = self.client.get(reverse("prices", args=["etf", "unknown"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_for_unknown_asset_class(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(reverse("prices", args=["crypto", "btc"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 400)
