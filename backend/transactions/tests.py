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

from transactions.views import sync_dividends_for_holdings

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
            price_native=None,
            amount_native=None,
            fx_rate=None,
            date="2026-01-15",
            type="BUY",
            average_price=None,
            price=None,
            amount=None,
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
            fx_rate=None,
            date="2026-01-15",
            type="BUY",
        )

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_with_fx_rate_override_skips_auto_resolve(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        """An explicit fx_rate in the request is used directly — the
        holding's market profile is never even looked up, since
        resolve_converted_amounts skips get_fx_rate_on_date entirely once
        an override is present (GitHub issue #149)."""
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_client.create_transaction.return_value = AVERAGE_TRANSACTION

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "average_price_native": 152.5,
                "fx_rate": 0.8,
                "date": "2026-01-15",
                "type": "BUY",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        mock_market_data_client.get_profile.assert_not_called()
        mock_market_data_client.get_fx_rate_on_date.assert_not_called()
        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            "AVERAGE",
            no_of_shares=10.0,
            average_price_native=152.5,
            average_price=122.0,
            price_native=None,
            price=None,
            amount_native=None,
            amount=None,
            fx_rate=0.8,
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
            fx_rate=None,
            date="2026-01-15",
            type="BUY",
        )
        mock_client.rewind_dividends_synced_through.assert_called_once_with(
            "auth0|abc123", "h-1", "2026-01-15"
        )

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_does_not_rewind_the_watermark_for_an_average_mode_buy(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        """GitHub issue #124's rewind is TRANSACTION-mode-only — AVERAGE
        mode's single BUY has no share-count timeline to reopen."""
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
        mock_client.rewind_dividends_synced_through.assert_not_called()

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
    def test_post_returns_400_for_non_positive_fx_rate(
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
        mock_client.create_transaction.side_effect = TransactionAmountError("bad")

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "average_price_native": 152.5,
                "fx_rate": 0,
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
            fx_rate=None,
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
            fx_rate=None,
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

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_fx_rate_only_recomputes_the_converted_value(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        """Patching just fx_rate (no date/native change) still triggers a
        recompute — and the override means get_fx_rate_on_date is never
        called (GitHub issue #149)."""
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = AVERAGE_PROFILE
        mock_client.get_transaction.return_value = AVERAGE_TRANSACTION
        updated = {**AVERAGE_TRANSACTION, "fx_rate": 0.82, "average_price": 125.05}
        mock_client.update_transaction.return_value = updated

        response = self.client.patch(
            reverse("transactions-detail", args=["h-1", "t-1"]),
            data={"fx_rate": 0.82},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), updated)
        mock_market_data_client.get_fx_rate_on_date.assert_not_called()
        mock_client.update_transaction.assert_called_once_with(
            "auth0|abc123", "h-1", "t-1", "AVERAGE", fx_rate=0.82, average_price=125.05
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
            "auth0|abc123",
            "h-1",
            "t-3",
            "TRANSACTION",
            amount_native=50.0,
            amount=None,
            fx_rate=None,
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
            dividends_native=0.0,
            dividends=0.0,
        )

    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_rewinds_the_watermark_for_a_transaction_mode_buy(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_client, mock_profile_client
    ) -> None:
        """GitHub issue #124: deleting a TRANSACTION-mode BUY/SELL changes
        the share-count timeline for every payout after it, the same as
        creating one does."""
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_transaction.return_value = BUY_TRANSACTION
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE
        mock_client.list_transactions.return_value = []

        response = self.client.delete(
            reverse("transactions-detail", args=["h-1", "t-2"]), **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_client.rewind_dividends_synced_through.assert_called_once_with(
            "auth0|abc123", "h-1", "2026-01-15"
        )

    @patch("transactions.views._profile_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_does_not_rewind_for_a_dividend_transaction(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_client, mock_profile_client
    ) -> None:
        """Deleting an auto-created DIVIDEND is the lasting correction
        issue #123's watermark exists for — it must never itself trigger a
        rewind, or the very payout the user just deleted would come right
        back on the next sync."""
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_transaction.return_value = DIVIDEND_TRANSACTION
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_profile_client.get_or_create_profile.return_value = TRANSACTION_PROFILE
        mock_client.list_transactions.return_value = []

        response = self.client.delete(
            reverse("transactions-detail", args=["h-1", "t-3"]), **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_client.rewind_dividends_synced_through.assert_not_called()

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


class SyncDividendsForHoldingsTests(TestCase):
    """GitHub issues #123 (AVERAGE mode) and #124 (TRANSACTION mode) —
    called directly by accounts/pies/holdings views.py's own
    _enrich_holdings/_enrich_holding, not through an HTTP endpoint of its
    own, so these call the function directly rather than going through
    self.client."""

    @patch("transactions.views._client")
    def test_skips_watchlist_and_fx_holdings_without_touching_transactions(
        self, mock_client
    ) -> None:
        result = sync_dividends_for_holdings(
            "auth0|abc123", [WATCHLIST_HOLDING, FX_HOLDING], AVERAGE_PROFILE
        )

        self.assertEqual(result, [WATCHLIST_HOLDING, FX_HOLDING])
        mock_client.list_transactions.assert_not_called()

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._client")
    def test_returns_the_holding_unchanged_when_nothing_new_to_sync(
        self, mock_client, mock_market_data_client
    ) -> None:
        mock_client.list_transactions.return_value = [AVERAGE_TRANSACTION]
        mock_client.get_dividends_synced_through.return_value = None
        mock_market_data_client.get_dividends.return_value = None

        result = sync_dividends_for_holdings("auth0|abc123", [ACCOUNT_HOLDING], AVERAGE_PROFILE)

        self.assertEqual(result, [ACCOUNT_HOLDING])
        mock_client.create_transaction.assert_not_called()
        mock_client.advance_dividends_synced_through.assert_not_called()

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    def test_creates_a_missing_paid_dividend_and_refreshes_the_holdings_rollup(
        self, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        mock_client.list_transactions.side_effect = [
            [AVERAGE_TRANSACTION],
            [AVERAGE_TRANSACTION, DIVIDEND_TRANSACTION],
        ]
        mock_client.get_dividends_synced_through.return_value = None
        mock_market_data_client.get_dividends.return_value = {
            "ticker": "AAPL",
            "currency": "USD",
            "last_updated": "2026-03-01",
            "dividends": [
                {
                    "ex_dividend_date": "2026-03-01",
                    "payment_date": None,
                    "price": 0.5,
                    "status": "paid",
                }
            ],
        }
        mock_market_data_client.get_profile.return_value = {"currency": "USD"}
        mock_market_data_client.get_fx_rate_on_date.return_value = 1.25
        refreshed_holding = {**ACCOUNT_HOLDING, "dividends_native": 5.0, "dividends": 6.25}
        mock_holdings_client.update_holding_financials.return_value = refreshed_holding

        result = sync_dividends_for_holdings("auth0|abc123", [ACCOUNT_HOLDING], AVERAGE_PROFILE)

        mock_market_data_client.get_dividends.assert_called_once_with("stock", "AAPL")
        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            "AVERAGE",
            external_id="dividend:2026-03-01",
            amount_native=5.0,
            date="2026-03-01",
            type="DIVIDEND",
            fx_rate=1.25,
            average_price=None,
            price=None,
            amount=6.25,
        )
        mock_holdings_client.update_holding_financials.assert_called_once()
        mock_client.advance_dividends_synced_through.assert_called_once_with(
            "auth0|abc123", "h-1", "2026-03-01"
        )
        self.assertEqual(result, [refreshed_holding])

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    def test_creates_a_transaction_mode_dividend_using_the_shares_held_on_ex_date(
        self, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        """GitHub issue #124: TRANSACTION mode's full BUY/SELL history
        means the correct share count for a payout depends on the running
        balance as of its own ex-date, not a single fixed BUY quantity —
        here 10 bought then 4 sold nets 6 shares held by the ex-date."""
        buy = {**BUY_TRANSACTION, "id": "t-buy", "no_of_shares": 10, "date": "2026-01-01"}
        sell = {
            **BUY_TRANSACTION,
            "id": "t-sell",
            "type": "SELL",
            "no_of_shares": 4,
            "date": "2026-02-01",
        }
        mock_client.list_transactions.side_effect = [[buy, sell], [buy, sell, DIVIDEND_TRANSACTION]]
        mock_client.get_dividends_synced_through.return_value = None
        mock_market_data_client.get_dividends.return_value = {
            "ticker": "AAPL",
            "currency": "USD",
            "last_updated": "2026-03-01",
            "dividends": [
                {
                    "ex_dividend_date": "2026-03-01",
                    "payment_date": None,
                    "price": 0.5,
                    "status": "paid",
                }
            ],
        }
        mock_market_data_client.get_profile.return_value = {"currency": "USD"}
        mock_market_data_client.get_fx_rate_on_date.return_value = 1.25
        refreshed_holding = {**ACCOUNT_HOLDING, "dividends_native": 3.0, "dividends": 3.75}
        mock_holdings_client.update_holding_financials.return_value = refreshed_holding

        result = sync_dividends_for_holdings("auth0|abc123", [ACCOUNT_HOLDING], TRANSACTION_PROFILE)

        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            "TRANSACTION",
            external_id="dividend:2026-03-01",
            amount_native=3.0,
            date="2026-03-01",
            type="DIVIDEND",
            fx_rate=1.25,
            average_price=None,
            price=None,
            amount=3.75,
        )
        self.assertEqual(result, [refreshed_holding])

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    def test_does_not_advance_the_watermark_when_a_create_fails(
        self, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        """A payout that fails to create (e.g. a transient
        TransactionAmountError) must never be marked as synced — advancing
        the watermark regardless would permanently skip it (and anything
        after it) on every future sync despite nothing ever actually being
        recorded, since compute_new_dividend_transactions treats
        `ex_date <= synced_through` as already handled either way."""
        mock_client.list_transactions.return_value = [AVERAGE_TRANSACTION]
        mock_client.get_dividends_synced_through.return_value = None
        mock_client.create_transaction.side_effect = TransactionAmountError("boom")
        mock_market_data_client.get_dividends.return_value = {
            "ticker": "AAPL",
            "currency": "USD",
            "last_updated": "2026-03-01",
            "dividends": [
                {
                    "ex_dividend_date": "2026-03-01",
                    "payment_date": None,
                    "price": 0.5,
                    "status": "paid",
                }
            ],
        }
        mock_market_data_client.get_profile.return_value = {"currency": "USD"}
        mock_market_data_client.get_fx_rate_on_date.return_value = 1.25

        sync_dividends_for_holdings("auth0|abc123", [ACCOUNT_HOLDING], AVERAGE_PROFILE)

        mock_client.create_transaction.assert_called_once()
        mock_client.advance_dividends_synced_through.assert_not_called()

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    def test_advances_the_watermark_when_every_create_in_the_batch_succeeds(
        self, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        """Two eligible payouts, both created successfully — the watermark
        must still advance to the latest one, same as a single-payout sync
        (see test_creates_a_missing_paid_dividend_and_refreshes_the_holdings_rollup)."""
        mock_client.list_transactions.return_value = [AVERAGE_TRANSACTION]
        mock_client.get_dividends_synced_through.return_value = None
        mock_market_data_client.get_dividends.return_value = {
            "ticker": "AAPL",
            "currency": "USD",
            "last_updated": "2026-06-01",
            "dividends": [
                {
                    "ex_dividend_date": "2026-03-01",
                    "payment_date": None,
                    "price": 0.5,
                    "status": "paid",
                },
                {
                    "ex_dividend_date": "2026-06-01",
                    "payment_date": None,
                    "price": 0.5,
                    "status": "paid",
                },
            ],
        }
        mock_market_data_client.get_profile.return_value = {"currency": "USD"}
        mock_market_data_client.get_fx_rate_on_date.return_value = 1.25
        mock_holdings_client.update_holding_financials.return_value = ACCOUNT_HOLDING

        sync_dividends_for_holdings("auth0|abc123", [ACCOUNT_HOLDING], AVERAGE_PROFILE)

        self.assertEqual(mock_client.create_transaction.call_count, 2)
        mock_client.advance_dividends_synced_through.assert_called_once_with(
            "auth0|abc123", "h-1", "2026-06-01"
        )

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    def test_a_conflict_exhaustion_runtimeerror_is_treated_like_any_other_create_failure(
        self, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        """A RuntimeError from create_transaction's own conflict-retry
        exhaustion (real-world trigger: two concurrent syncs racing to
        write the same holding, e.g. React StrictMode double-mounting an
        effect in dev) must not silently advance that holding's watermark —
        same "don't mark a failed create as synced" rule as
        TransactionAmountError — while a *different* holding in the same
        batch, unaffected by the race, still syncs normally."""

        def create_transaction(user_id, holding_id, mode, **fields):
            if holding_id == "h-1":
                raise RuntimeError("Too many conflicting writes to transactions for holding 'h-1'.")
            return {"id": "t-new"}

        def update_holding_financials(user_id, holding_id, **rollup):
            return ACCOUNT_HOLDING if holding_id == "h-1" else PIE_HOLDING

        mock_client.list_transactions.return_value = [AVERAGE_TRANSACTION]
        mock_client.get_dividends_synced_through.return_value = None
        mock_client.create_transaction.side_effect = create_transaction
        mock_market_data_client.get_dividends.return_value = {
            "ticker": "AAPL",
            "currency": "USD",
            "last_updated": "2026-03-01",
            "dividends": [
                {
                    "ex_dividend_date": "2026-03-01",
                    "payment_date": None,
                    "price": 0.5,
                    "status": "paid",
                }
            ],
        }
        mock_market_data_client.get_profile.return_value = {"currency": "USD"}
        mock_market_data_client.get_fx_rate_on_date.return_value = 1.25
        mock_holdings_client.update_holding_financials.side_effect = update_holding_financials

        result = sync_dividends_for_holdings(
            "auth0|abc123", [ACCOUNT_HOLDING, PIE_HOLDING], AVERAGE_PROFILE
        )

        self.assertEqual(mock_client.create_transaction.call_count, 2)
        # Only h-2 (unaffected by the race) advances — h-1's failed create
        # must not be marked as synced.
        mock_client.advance_dividends_synced_through.assert_called_once_with(
            "auth0|abc123", "h-2", "2026-03-01"
        )
        self.assertEqual(result, [ACCOUNT_HOLDING, PIE_HOLDING])

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    def test_an_unexpected_error_on_one_holding_does_not_abort_the_rest_of_the_batch(
        self, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        """Something failing well before create_transaction (here,
        get_dividends itself) for one holding must not propagate out of
        the whole function and abandon every holding still left in the
        batch — GitHub issue reproduced against a real local import where
        exactly this kind of per-holding failure silently zeroed out
        several holdings' dividends at once."""
        mock_client.list_transactions.return_value = [AVERAGE_TRANSACTION]
        mock_client.get_dividends_synced_through.return_value = None
        mock_market_data_client.get_dividends.side_effect = [
            RuntimeError("market data unavailable"),
            {
                "ticker": "AAPL",
                "currency": "USD",
                "last_updated": "2026-03-01",
                "dividends": [
                    {
                        "ex_dividend_date": "2026-03-01",
                        "payment_date": None,
                        "price": 0.5,
                        "status": "paid",
                    }
                ],
            },
        ]
        mock_market_data_client.get_profile.return_value = {"currency": "USD"}
        mock_market_data_client.get_fx_rate_on_date.return_value = 1.25
        mock_holdings_client.update_holding_financials.return_value = PIE_HOLDING

        result = sync_dividends_for_holdings(
            "auth0|abc123", [ACCOUNT_HOLDING, PIE_HOLDING], AVERAGE_PROFILE
        )

        # h-1's get_dividends blew up; h-2 (processed next) still synced
        # normally.
        mock_client.create_transaction.assert_called_once()
        mock_client.advance_dividends_synced_through.assert_called_once_with(
            "auth0|abc123", "h-2", "2026-03-01"
        )
        self.assertEqual(result, [ACCOUNT_HOLDING, PIE_HOLDING])

    @patch("transactions.views._market_data_client")
    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    def test_a_concurrent_caller_already_creating_the_payout_still_advances_the_watermark(
        self, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        """create_transaction raising TransactionAlreadyExistsError for the
        external_id dedup case (see TransactionsClient.create_transaction)
        means a concurrent sync already created this exact payout — that's
        a success, not a failure, so it must not block the watermark from
        advancing the way a genuine create failure does."""
        mock_client.list_transactions.return_value = [AVERAGE_TRANSACTION]
        mock_client.get_dividends_synced_through.return_value = None
        mock_client.create_transaction.side_effect = TransactionAlreadyExistsError(
            "A transaction with external_id 'dividend:2026-03-01' already exists."
        )
        mock_market_data_client.get_dividends.return_value = {
            "ticker": "AAPL",
            "currency": "USD",
            "last_updated": "2026-03-01",
            "dividends": [
                {
                    "ex_dividend_date": "2026-03-01",
                    "payment_date": None,
                    "price": 0.5,
                    "status": "paid",
                }
            ],
        }
        mock_market_data_client.get_profile.return_value = {"currency": "USD"}
        mock_market_data_client.get_fx_rate_on_date.return_value = 1.25
        mock_holdings_client.update_holding_financials.return_value = ACCOUNT_HOLDING

        sync_dividends_for_holdings("auth0|abc123", [ACCOUNT_HOLDING], AVERAGE_PROFILE)

        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            "AVERAGE",
            external_id="dividend:2026-03-01",
            amount_native=5.0,
            date="2026-03-01",
            type="DIVIDEND",
            fx_rate=1.25,
            average_price=None,
            price=None,
            amount=6.25,
        )
        mock_client.advance_dividends_synced_through.assert_called_once_with(
            "auth0|abc123", "h-1", "2026-03-01"
        )
