from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import HoldingAlreadyExistsError, HoldingLimitExceededError, HoldingNotFoundError

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}
HOLDING = {
    "id": "h-1",
    "ticker": "AAPL",
    "asset_class": "stock",
    "account_id": "acc-1",
    "pie_id": None,
    "watchlist_id": None,
    "timestamp": "2026-01-01T00:00:00+00:00",
}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class HoldingListViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("holdings-list"))

        self.assertEqual(response.status_code, 401)

    def test_post_without_trailing_slash_returns_404_not_500(self) -> None:
        """Same APPEND_SLASH regression test as accounts/tests.py."""
        response = self.client.post(
            "/api/holdings", data={}, content_type="application/json", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 404)

    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_users_holdings(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_holdings.return_value = [HOLDING]

        response = self.client.get(reverse("holdings-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [HOLDING])
        mock_client.list_holdings.assert_called_once_with(
            "auth0|abc123", account_id=None, pie_id=None, watchlist_id=None
        )

    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_filters_by_a_single_parent_query_param(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_holdings.return_value = [HOLDING]

        response = self.client.get(reverse("holdings-list"), {"account_id": "acc-1"}, **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        mock_client.list_holdings.assert_called_once_with(
            "auth0|abc123", account_id="acc-1", pie_id=None, watchlist_id=None
        )

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_400_when_more_than_one_parent_filter_given(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.get(
            reverse("holdings-list"), {"account_id": "acc-1", "pie_id": "pie-1"}, **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_a_required_field_is_missing(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "AAPL"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_pie_id_given(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "VOO", "asset_class": "etf", "pie_id": "pie-1"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_neither_account_id_nor_watchlist_id_given(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "AAPL", "asset_class": "stock"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_both_account_id_and_watchlist_id_given(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("holdings-list"),
            data={
                "ticker": "AAPL",
                "asset_class": "stock",
                "account_id": "acc-1",
                "watchlist_id": "watch-1",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_unknown_asset_class(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "AAPL", "asset_class": "crypto", "account_id": "acc-1"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("holdings.views._accounts_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_unknown_or_foreign_account_id(
        self, mock_jwks_client, mock_decode, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [{"id": "some-other-account"}]

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "AAPL", "asset_class": "stock", "account_id": "not-mine"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("holdings.views._watchlists_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_unknown_or_foreign_watchlist_id(
        self, mock_jwks_client, mock_decode, mock_watchlists_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_watchlists_client.list_watchlists.return_value = [{"id": "some-other-watchlist"}]

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "AAPL", "asset_class": "stock", "watchlist_id": "not-mine"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("holdings.views._market_data_client")
    @patch("holdings.views._accounts_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_ticker_has_no_market_data(
        self, mock_jwks_client, mock_decode, mock_accounts_client, mock_market_data_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [{"id": "acc-1"}]
        mock_market_data_client.get_profile.return_value = None

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "NOPE", "asset_class": "stock", "account_id": "acc-1"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("holdings.views._market_data_client")
    @patch("holdings.views._accounts_client")
    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_a_holding_under_account_and_uppercases_the_ticker(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_accounts_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [{"id": "acc-1"}]
        mock_market_data_client.get_profile.return_value = {"ticker": "AAPL"}
        mock_client.create_holding.return_value = HOLDING

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "aapl", "asset_class": "stock", "account_id": "acc-1"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), HOLDING)
        mock_market_data_client.get_profile.assert_called_once_with("stock", "AAPL")
        mock_client.create_holding.assert_called_once_with(
            "auth0|abc123",
            ticker="AAPL",
            asset_class="stock",
            account_id="acc-1",
            watchlist_id=None,
        )

    @patch("holdings.views._market_data_client")
    @patch("holdings.views._watchlists_client")
    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_a_holding_under_watchlist(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_watchlists_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_watchlists_client.list_watchlists.return_value = [{"id": "watch-1"}]
        mock_market_data_client.get_profile.return_value = {"ticker": "EURUSD"}
        watchlist_holding = {**HOLDING, "account_id": None, "watchlist_id": "watch-1"}
        mock_client.create_holding.return_value = watchlist_holding

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "EURUSD", "asset_class": "fx", "watchlist_id": "watch-1"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        mock_client.create_holding.assert_called_once_with(
            "auth0|abc123",
            ticker="EURUSD",
            asset_class="fx",
            account_id=None,
            watchlist_id="watch-1",
        )

    @patch("holdings.views._market_data_client")
    @patch("holdings.views._accounts_client")
    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_for_duplicate_ticker(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_accounts_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [{"id": "acc-1"}]
        mock_market_data_client.get_profile.return_value = {"ticker": "AAPL"}
        mock_client.create_holding.side_effect = HoldingAlreadyExistsError("dup")

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "AAPL", "asset_class": "stock", "account_id": "acc-1"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("holdings.views._market_data_client")
    @patch("holdings.views._accounts_client")
    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_when_holding_limit_reached(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_accounts_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [{"id": "acc-1"}]
        mock_market_data_client.get_profile.return_value = {"ticker": "AAPL"}
        mock_client.create_holding.side_effect = HoldingLimitExceededError("limit")
        mock_client.max_holdings_for_account = 100

        response = self.client.post(
            reverse("holdings-list"),
            data={"ticker": "AAPL", "asset_class": "stock", "account_id": "acc-1"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)


class HoldingDetailViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("holdings-detail", args=["h-1"]))

        self.assertEqual(response.status_code, 401)

    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_holding(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_holding.return_value = HOLDING

        response = self.client.get(reverse("holdings-detail", args=["h-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), HOLDING)
        mock_client.get_holding.assert_called_once_with("auth0|abc123", "h-1")

    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_404_for_unknown_holding(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_holding.side_effect = HoldingNotFoundError("no such holding")

        response = self.client.get(reverse("holdings-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)

    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_removes_the_holding(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.delete(reverse("holdings-detail", args=["h-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 204)
        mock_client.delete_holding.assert_called_once_with("auth0|abc123", "h-1")

    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_404_for_unknown_holding(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.delete_holding.side_effect = HoldingNotFoundError("no such holding")

        response = self.client.delete(reverse("holdings-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)

    @patch("holdings.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_400_for_pie_scoped_holding(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.delete_holding.side_effect = ValueError("pie-scoped")

        response = self.client.delete(reverse("holdings-detail", args=["h-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 400)
