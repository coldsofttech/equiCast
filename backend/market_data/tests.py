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
    def test_returns_price_series_for_the_default_range(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_prices.return_value = {
            "ticker": "VOO",
            "currency": "USD",
            "last_updated": "2026-01-02T21:00:00+00:00",
            "source": "yfinance",
            "prices": [{"date": "2026-01-02", "open": 1, "high": 2, "low": 0.5, "close": 1.5}],
        }

        response = self.client.get(reverse("prices", args=["etf", "voo"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticker"], "VOO")
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(
            data["prices"], [{"date": "2026-01-02", "open": 1, "high": 2, "low": 0.5, "close": 1.5}]
        )
        mock_client.get_prices.assert_called_once_with("etf", "voo", price_range="max")

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_range_query_param_is_passed_through(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_prices.return_value = {
            "ticker": "VOO",
            "currency": "USD",
            "last_updated": None,
            "source": None,
            "prices": [],
        }

        self.client.get(reverse("prices", args=["etf", "voo"]), {"range": "1y"}, **AUTH_HEADER)

        mock_client.get_prices.assert_called_once_with("etf", "voo", price_range="1y")

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_for_unknown_range(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(
            reverse("prices", args=["etf", "voo"]), {"range": "3d"}, **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 400)

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_empty_prices_when_no_data(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_prices.return_value = {
            "ticker": "UNKNOWN",
            "currency": None,
            "last_updated": None,
            "source": None,
            "prices": [],
        }

        response = self.client.get(reverse("prices", args=["etf", "unknown"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["prices"], [])

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_for_unknown_asset_class(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(reverse("prices", args=["crypto", "btc"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 400)


class SearchViewTests(TestCase):
    def test_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("search"), {"q": "v"})

        self.assertEqual(response.status_code, 401)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_when_q_missing(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(reverse("search"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_when_q_is_empty(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(reverse("search"), {"q": ""}, **AUTH_HEADER)

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_for_unknown_asset_class(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(
            reverse("search"), {"q": "v", "asset_class": "crypto"}, **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 400)

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_matches_with_default_pagination(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.search.return_value = [
            {"ticker": "V", "name": "Visa Inc.", "type": "stock", "current_price": 310.2}
        ]

        response = self.client.get(reverse("search"), {"q": "v"}, **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 50)
        self.assertEqual(data["total_pages"], 1)
        self.assertEqual(
            data["results"],
            [{"ticker": "V", "name": "Visa Inc.", "type": "stock", "current_price": 310.2}],
        )
        mock_client.search.assert_called_once_with(
            "v", asset_classes=None, min_market_cap=None, max_market_cap=None
        )

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_asset_class_filter_is_passed_through(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.search.return_value = []

        self.client.get(reverse("search"), {"q": "v", "asset_class": "stock"}, **AUTH_HEADER)

        mock_client.search.assert_called_once_with(
            "v", asset_classes=["stock"], min_market_cap=None, max_market_cap=None
        )

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_market_cap_bounds_are_passed_through(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.search.return_value = []

        self.client.get(
            reverse("search"),
            {"q": "v", "min_market_cap": "1000000000", "max_market_cap": "2000000000.5"},
            **AUTH_HEADER,
        )

        mock_client.search.assert_called_once_with(
            "v", asset_classes=None, min_market_cap=1_000_000_000.0, max_market_cap=2_000_000_000.5
        )

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_for_non_numeric_market_cap(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(
            reverse("search"), {"q": "v", "min_market_cap": "x"}, **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_when_min_market_cap_exceeds_max(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(
            reverse("search"),
            {"q": "v", "min_market_cap": "2000", "max_market_cap": "1000"},
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_paginates_results(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.search.return_value = [
            {"ticker": f"T{i}", "name": f"Ticker {i}", "type": "stock", "current_price": i}
            for i in range(5)
        ]

        response = self.client.get(
            reverse("search"), {"q": "t", "page": "2", "page_size": "2"}, **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 5)
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["page_size"], 2)
        self.assertEqual(data["total_pages"], 3)
        self.assertEqual([r["ticker"] for r in data["results"]], ["T2", "T3"])

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_for_non_integer_page(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(reverse("search"), {"q": "v", "page": "x"}, **AUTH_HEADER)

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_400_for_non_positive_page(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(reverse("search"), {"q": "v", "page": "0"}, **AUTH_HEADER)

        self.assertEqual(response.status_code, 400)

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_page_size_is_capped(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.search.return_value = []

        response = self.client.get(
            reverse("search"), {"q": "v", "page_size": "1000"}, **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page_size"], 200)

    @patch("market_data.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_returns_empty_results_when_no_match(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.search.return_value = []

        response = self.client.get(reverse("search"), {"q": "zzz"}, **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["total_pages"], 0)
        self.assertEqual(data["results"], [])
