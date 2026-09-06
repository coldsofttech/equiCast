from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import (
    HoldingNotFoundError,
    InsufficientSharesError,
    TransactionAlreadyExistsError,
    TransactionAmountError,
    TransactionLimitExceededError,
    TransactionNotFoundError,
)

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}

ACCOUNT_HOLDING = {
    "id": "h-1",
    "ticker": "AAPL",
    "asset_class": "stock",
    "account_id": "acc-1",
    "pie_id": None,
    "watchlist_id": None,
    "timestamp": "2026-01-01T00:00:00+00:00",
}
PIE_HOLDING = {**ACCOUNT_HOLDING, "id": "h-2", "account_id": None, "pie_id": "pie-1"}
WATCHLIST_HOLDING = {
    **ACCOUNT_HOLDING,
    "id": "h-3",
    "account_id": None,
    "watchlist_id": "watch-1",
}
FX_HOLDING = {**ACCOUNT_HOLDING, "id": "h-4", "asset_class": "fx"}

#: transaction_type is a single per-user profile setting now, not an
#: account field — see UserProfileClient/resolve_transaction_mode.
#: default_currency is needed by resolve_converted_amounts, called on every
#: successful create/update.
AVERAGE_PROFILE = {"transaction_type": "AVERAGE", "default_currency": "GBP"}
TRANSACTION_PROFILE = {"transaction_type": "TRANSACTION", "default_currency": "GBP"}

AVERAGE_TRANSACTION = {
    "id": "t-1",
    "holding_id": "h-1",
    "no_of_shares": 10,
    "average_price_native": 152.5,
    "average_price": 152.5,
    "price_native": None,
    "price": None,
    "amount_native": None,
    "amount": None,
    "date": "2026-01-15",
    "type": "BUY",
    "created_at": "2026-01-15T00:00:00+00:00",
    "updated_at": "2026-01-15T00:00:00+00:00",
}
BUY_TRANSACTION = {
    "id": "t-2",
    "holding_id": "h-1",
    "no_of_shares": 10,
    "average_price_native": None,
    "average_price": None,
    "price_native": 152.5,
    "price": 152.5,
    "amount_native": None,
    "amount": None,
    "date": "2026-01-15",
    "type": "BUY",
    "created_at": "2026-01-15T00:00:00+00:00",
    "updated_at": "2026-01-15T00:00:00+00:00",
}
DIVIDEND_TRANSACTION = {
    "id": "t-3",
    "holding_id": "h-1",
    "no_of_shares": None,
    "average_price_native": None,
    "average_price": None,
    "price_native": None,
    "price": None,
    "amount_native": 42.10,
    "amount": 42.10,
    "date": "2026-03-01",
    "type": "DIVIDEND",
    "created_at": "2026-03-01T00:00:00+00:00",
    "updated_at": "2026-03-01T00:00:00+00:00",
}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class TransactionListViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("transactions-list"))

        self.assertEqual(response.status_code, 401)

    def test_post_without_trailing_slash_returns_404_not_500(self) -> None:
        """Same APPEND_SLASH regression test as accounts/tests.py."""
        response = self.client.post(
            "/api/transactions", data={}, content_type="application/json", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 404)

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_users_transactions(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_transactions.return_value = [AVERAGE_TRANSACTION]

        response = self.client.get(reverse("transactions-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertIsNone(body["next"])
        self.assertIsNone(body["previous"])
        self.assertEqual(body["results"], [AVERAGE_TRANSACTION])
        mock_client.list_transactions.assert_called_once_with(
            "auth0|abc123", holding_id=None, year=None, date_from=None, date_to=None
        )

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_sorts_most_recent_date_first(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        older = {**AVERAGE_TRANSACTION, "id": "t-old", "date": "2025-01-01"}
        newer = {**AVERAGE_TRANSACTION, "id": "t-new", "date": "2026-06-01"}
        mock_client.list_transactions.return_value = [older, newer]

        response = self.client.get(reverse("transactions-list"), **AUTH_HEADER)

        body = response.json()
        self.assertEqual([t["id"] for t in body["results"]], ["t-new", "t-old"])
        self.assertEqual(body["count"], 2)

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_paginates_at_50_per_page(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        records = [{**AVERAGE_TRANSACTION, "id": f"t-{i}", "date": "2026-01-01"} for i in range(60)]
        mock_client.list_transactions.return_value = records

        first_page = self.client.get(reverse("transactions-list"), **AUTH_HEADER)
        second_page = self.client.get(
            reverse("transactions-list"), {"page": "2"}, **AUTH_HEADER
        )

        first_body = first_page.json()
        second_body = second_page.json()
        self.assertEqual(len(first_body["results"]), 50)
        self.assertIsNotNone(first_body["next"])
        self.assertEqual(len(second_body["results"]), 10)
        self.assertIsNone(second_body["next"])

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_filters_by_holding_id(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_transactions.return_value = [AVERAGE_TRANSACTION]

        response = self.client.get(
            reverse("transactions-list"), {"holding_id": "h-1"}, **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 200)
        mock_client.list_transactions.assert_called_once_with(
            "auth0|abc123", holding_id="h-1", year=None, date_from=None, date_to=None
        )

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_filters_by_year_and_date_range(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_transactions.return_value = [BUY_TRANSACTION]

        response = self.client.get(
            reverse("transactions-list"),
            {
                "holding_id": "h-1",
                "year": "2026",
                "date_from": "2026-01-01",
                "date_to": "2026-06-30",
            },
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        mock_client.list_transactions.assert_called_once_with(
            "auth0|abc123",
            holding_id="h-1",
            year="2026",
            date_from="2026-01-01",
            date_to="2026-06-30",
        )

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_holding_id_missing(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("transactions-list"),
            data={"no_of_shares": 1, "average_price": 1},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_unknown_holding_id(
        self, mock_jwks_client, mock_decode, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.side_effect = HoldingNotFoundError("no such holding")

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "missing", "no_of_shares": 1, "average_price": 1},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_watchlist_scoped_holding(
        self, mock_jwks_client, mock_decode, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = WATCHLIST_HOLDING

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-3", "no_of_shares": 1, "average_price": 1},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_fx_holding(
        self, mock_jwks_client, mock_decode, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = FX_HOLDING

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-4", "no_of_shares": 1, "average_price": 1},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_a_transaction_for_a_pie_scoped_holding(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        """transaction_type is a single per-user setting now (see
        UserProfileClient) — resolving it no longer depends on whether the
        holding is pie-scoped or account-direct, unlike before."""
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = PIE_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_market_data_client.get_profile.return_value = None
        mock_client.create_transaction.return_value = {**AVERAGE_TRANSACTION, "holding_id": "h-2"}

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-2",
                "no_of_shares": 10,
                "average_price_native": 152.5,
                "date": "2026-01-15",
                "type": "BUY",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-2",
            "AVERAGE",
            no_of_shares=10.0,
            average_price_native=152.5,
            average_price=None,
            price_native=None,
            price=None,
            amount_native=None,
            amount=None,
            date="2026-01-15",
            type="BUY",
        )

    @patch("transactions.views._profile_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_average_fields_missing(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_profile_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE

        response = self.client.post(
            reverse("transactions-list"),
            # average_price missing.
            data={"holding_id": "h-1", "no_of_shares": 10, "type": "BUY", "date": "2026-01-15"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._profile_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_average_payload_has_a_field_not_applicable(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_profile_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "average_price": 100,
                "date": "2026-01-01",
                "type": "BUY",
                # price isn't applicable to an AVERAGE-mode BUY.
                "price": 100,
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_an_average_transaction(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_market_data_client.get_profile.return_value = None
        mock_client.create_transaction.return_value = AVERAGE_TRANSACTION

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "average_price_native": 152.5,
                "date": "2026-01-15",
                "type": "BUY",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), AVERAGE_TRANSACTION)
        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            "AVERAGE",
            no_of_shares=10.0,
            average_price_native=152.5,
            average_price=None,
            price_native=None,
            price=None,
            amount_native=None,
            amount=None,
            date="2026-01-15",
            type="BUY",
        )

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_for_second_average_transaction(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_market_data_client.get_profile.return_value = None
        mock_client.create_transaction.side_effect = TransactionAlreadyExistsError("dup")

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "average_price_native": 152.5,
                "date": "2026-01-15",
                "type": "BUY",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("transactions.views._profile_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_transaction_fields_missing(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_profile_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-1", "no_of_shares": 10, "price": 100},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._profile_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_invalid_type(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_profile_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "price": 100,
                "date": "2026-01-01",
                "type": "HOLD",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_a_buy_transaction(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE
        mock_market_data_client.get_profile.return_value = None
        mock_client.create_transaction.return_value = BUY_TRANSACTION

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "price_native": 152.5,
                "date": "2026-01-15",
                "type": "BUY",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), BUY_TRANSACTION)
        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            "TRANSACTION",
            no_of_shares=10.0,
            average_price_native=None,
            average_price=None,
            price_native=152.5,
            price=None,
            amount_native=None,
            amount=None,
            date="2026-01-15",
            type="BUY",
        )

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_when_sell_exceeds_net_shares(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE
        mock_market_data_client.get_profile.return_value = None
        mock_client.create_transaction.side_effect = InsufficientSharesError("nope")

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "price_native": 152.5,
                "date": "2026-01-15",
                "type": "SELL",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_when_transaction_limit_reached(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE
        mock_market_data_client.get_profile.return_value = None
        mock_client.create_transaction.side_effect = TransactionLimitExceededError("limit")
        mock_client.max_transactions_for_holding = 500

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "price_native": 152.5,
                "date": "2026-01-15",
                "type": "BUY",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_non_positive_amount(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_client.create_transaction.side_effect = TransactionAmountError("bad")

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 0,
                "average_price": 152.5,
                "date": "2026-01-15",
                "type": "BUY",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_a_dividend_transaction_in_average_mode(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_market_data_client.get_profile.return_value = None
        mock_client.create_transaction.return_value = DIVIDEND_TRANSACTION

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "type": "DIVIDEND",
                "amount_native": 42.10,
                "date": "2026-03-01",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), DIVIDEND_TRANSACTION)
        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            "AVERAGE",
            no_of_shares=None,
            average_price_native=None,
            average_price=None,
            price_native=None,
            price=None,
            amount_native=42.10,
            amount=None,
            date="2026-03-01",
            type="DIVIDEND",
        )

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_a_dividend_transaction_in_transaction_mode(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE
        mock_market_data_client.get_profile.return_value = None
        mock_client.create_transaction.return_value = DIVIDEND_TRANSACTION

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "type": "DIVIDEND",
                "amount_native": 42.10,
                "date": "2026-03-01",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), DIVIDEND_TRANSACTION)
        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            "TRANSACTION",
            no_of_shares=None,
            average_price_native=None,
            average_price=None,
            price_native=None,
            price=None,
            amount_native=42.10,
            amount=None,
            date="2026-03-01",
            type="DIVIDEND",
        )


class TransactionDetailViewTests(TestCase):
    """Addressed by holding_id/transaction_id together — see
    transactions/urls.py — so every call below passes both."""

    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("transactions-detail", args=["h-1", "t-1"]))

        self.assertEqual(response.status_code, 401)

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_transaction(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_transaction.return_value = AVERAGE_TRANSACTION

        response = self.client.get(
            reverse("transactions-detail", args=["h-1", "t-1"]), **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), AVERAGE_TRANSACTION)
        mock_client.get_transaction.assert_called_once_with("auth0|abc123", "h-1", "t-1")

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_404_for_unknown_transaction(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_transaction.side_effect = TransactionNotFoundError("no such transaction")

        response = self.client.get(
            reverse("transactions-detail", args=["h-1", "missing"]), **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 404)

    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_404_for_unknown_holding_id(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
    ) -> None:
        """PATCH now resolves the holding (and, via it, the caller's
        transaction_type) before touching the transaction itself — an
        unknown holding_id is a new failure mode this adds."""
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.side_effect = HoldingNotFoundError("no such holding")

        response = self.client.patch(
            reverse("transactions-detail", args=["missing", "t-1"]),
            data={"no_of_shares": 15},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 404)
        mock_client.update_transaction.assert_not_called()

    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_an_average_transaction(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        updated = {**AVERAGE_TRANSACTION, "no_of_shares": 15}
        mock_client.update_transaction.return_value = updated

        response = self.client.patch(
            reverse("transactions-detail", args=["h-1", "t-1"]),
            data={"no_of_shares": 15},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), updated)
        mock_client.update_transaction.assert_called_once_with(
            "auth0|abc123", "h-1", "t-1", "AVERAGE", no_of_shares=15
        )

    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_404_for_unknown_transaction(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_client.update_transaction.side_effect = TransactionNotFoundError("no such transaction")

        response = self.client.patch(
            reverse("transactions-detail", args=["h-1", "missing"]),
            data={"no_of_shares": 15},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 404)

    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_400_for_transaction_mode_buy_sell_record(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE
        mock_client.update_transaction.side_effect = ValueError("immutable")

        response = self.client.patch(
            reverse("transactions-detail", args=["h-1", "t-2"]),
            data={"no_of_shares": 15},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_400_for_non_positive_amount(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_client.update_transaction.side_effect = TransactionAmountError("bad")

        response = self.client.patch(
            reverse("transactions-detail", args=["h-1", "t-1"]),
            data={"no_of_shares": 0},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_a_dividend_record_in_transaction_mode(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        """A DIVIDEND record is mutable even under TRANSACTION mode, unlike
        a BUY/SELL record — see equicast_core.transactions. Patching
        amount_native re-resolves the converted amount (see
        resolve_converted_amounts), so this needs get_transaction (to read
        the existing record's date/type) and _market_data_client mocked the
        same as a create."""
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE
        mock_market_data_client.get_profile.return_value = None
        mock_client.get_transaction.return_value = DIVIDEND_TRANSACTION
        updated = {**DIVIDEND_TRANSACTION, "amount_native": 50, "amount": None}
        mock_client.update_transaction.return_value = updated

        response = self.client.patch(
            reverse("transactions-detail", args=["h-1", "t-3"]),
            data={"amount_native": 50},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), updated)
        mock_client.update_transaction.assert_called_once_with(
            "auth0|abc123", "h-1", "t-3", "TRANSACTION", amount_native=50.0, amount=None
        )

    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_removes_the_transaction(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_client, mock_profile_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_client.list_transactions.return_value = []

        response = self.client.delete(
            reverse("transactions-detail", args=["h-1", "t-1"]), **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_client.delete_transaction.assert_called_once_with("auth0|abc123", "h-1", "t-1")
        mock_holdings_client.update_holding_financials.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            no_of_shares=0,
            average_price_native=None,
            average_price=None,
            invested_native=0,
            invested=0,
        )

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_404_for_unknown_transaction(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.delete_transaction.side_effect = TransactionNotFoundError("no such transaction")

        response = self.client.delete(
            reverse("transactions-detail", args=["h-1", "missing"]), **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 404)
