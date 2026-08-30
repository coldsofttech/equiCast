from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class ProfileViewTests(TestCase):
    @patch("market_data.views._client")
    def test_returns_profile_for_known_symbol(self, mock_client) -> None:
        mock_client.get_profile.return_value = {"ticker": "AAPL", "name": "Apple Inc."}

        response = self.client.get(reverse("profile", args=["stock", "aapl"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ticker": "AAPL", "name": "Apple Inc."})
        mock_client.get_profile.assert_called_once_with("stock", "aapl")

    @patch("market_data.views._client")
    def test_returns_404_when_symbol_not_found(self, mock_client) -> None:
        mock_client.get_profile.return_value = None

        response = self.client.get(reverse("profile", args=["stock", "unknown"]))

        self.assertEqual(response.status_code, 404)

    def test_returns_400_for_unknown_asset_class(self) -> None:
        response = self.client.get(reverse("profile", args=["crypto", "btc"]))

        self.assertEqual(response.status_code, 400)


class PricesViewTests(TestCase):
    @patch("market_data.views._client")
    def test_returns_price_records(self, mock_client) -> None:
        mock_client.get_prices.return_value = [{"ticker": "VOO", "date": "2026-01-02"}]

        response = self.client.get(reverse("prices", args=["etf", "voo"]))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "VOO")
        self.assertEqual(data["results"], [{"ticker": "VOO", "date": "2026-01-02"}])
        mock_client.get_prices.assert_called_once_with("etf", "voo")

    @patch("market_data.views._client")
    def test_returns_empty_results_when_no_data(self, mock_client) -> None:
        mock_client.get_prices.return_value = []

        response = self.client.get(reverse("prices", args=["etf", "unknown"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_returns_400_for_unknown_asset_class(self) -> None:
        response = self.client.get(reverse("prices", args=["crypto", "btc"]))

        self.assertEqual(response.status_code, 400)
