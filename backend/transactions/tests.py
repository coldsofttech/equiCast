from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import (
    AccountNotFoundError,
    HoldingNotFoundError,
    InsufficientSharesError,
    PieNotFoundError,
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

AVERAGE_ACCOUNT = {"id": "acc-1", "transaction_type": "AVERAGE"}
TRANSACTION_ACCOUNT = {"id": "acc-1", "transaction_type": "TRANSACTION"}
PIE = {"id": "pie-1", "account_id": "acc-1"}

AVERAGE_TRANSACTION = {
    "id": "t-1",
    "holding_id": "h-1",
    "no_of_shares": 10,
    "average_price": 152.5,
    "price": None,
    "date": None,
    "type": None,
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}
BUY_TRANSACTION = {
    "id": "t-2",
    "holding_id": "h-1",
    "no_of_shares": 10,
    "average_price": None,
    "price": 152.5,
    "date": "2026-01-15",
    "type": "BUY",
    "created_at": "2026-01-15T00:00:00+00:00",
    "updated_at": "2026-01-15T00:00:00+00:00",
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
        self.assertEqual(response.json(), [AVERAGE_TRANSACTION])
        mock_client.list_transactions.assert_called_once_with(
            "auth0|abc123", holding_id=None, year=None, date_from=None, date_to=None
        )

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

    @patch("transactions.views._accounts_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_account_no_longer_exists(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.side_effect = AccountNotFoundError("gone")

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-1", "no_of_shares": 1, "average_price": 1},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._accounts_client")
    @patch("transactions.views._pies_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_pie_no_longer_exists(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_pies_client,
        mock_accounts_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = PIE_HOLDING
        mock_pies_client.get_pie.side_effect = PieNotFoundError("gone")

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-2", "no_of_shares": 1, "average_price": 1},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)
        mock_accounts_client.get_account.assert_not_called()

    @patch("transactions.views._accounts_client")
    @patch("transactions.views._pies_client")
    @patch("transactions.views._client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_resolves_mode_via_pie_account(
        self,
        mock_jwks_client,
        mock_decode,
        mock_holdings_client,
        mock_client,
        mock_pies_client,
        mock_accounts_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = PIE_HOLDING
        mock_pies_client.get_pie.return_value = PIE
        mock_accounts_client.get_account.return_value = AVERAGE_ACCOUNT
        mock_client.create_transaction.return_value = {**AVERAGE_TRANSACTION, "holding_id": "h-2"}

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-2", "no_of_shares": 10, "average_price": 152.5},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        mock_pies_client.get_pie.assert_called_once_with("auth0|abc123", "pie-1")
        mock_accounts_client.get_account.assert_called_once_with("auth0|abc123", "acc-1")
        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-2",
            "AVERAGE",
            no_of_shares=10,
            average_price=152.5,
            price=None,
            date=None,
            type=None,
        )

    @patch("transactions.views._accounts_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_average_fields_missing(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = AVERAGE_ACCOUNT

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-1", "no_of_shares": 10},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._accounts_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_average_payload_has_transaction_fields(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = AVERAGE_ACCOUNT

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "average_price": 100,
                "date": "2026-01-01",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._accounts_client")
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
        mock_accounts_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = AVERAGE_ACCOUNT
        mock_client.create_transaction.return_value = AVERAGE_TRANSACTION

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-1", "no_of_shares": 10, "average_price": 152.5},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), AVERAGE_TRANSACTION)
        mock_client.create_transaction.assert_called_once_with(
            "auth0|abc123",
            "h-1",
            "AVERAGE",
            no_of_shares=10,
            average_price=152.5,
            price=None,
            date=None,
            type=None,
        )

    @patch("transactions.views._accounts_client")
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
        mock_accounts_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = AVERAGE_ACCOUNT
        mock_client.create_transaction.side_effect = TransactionAlreadyExistsError("dup")

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-1", "no_of_shares": 10, "average_price": 152.5},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("transactions.views._accounts_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_transaction_fields_missing(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = TRANSACTION_ACCOUNT

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-1", "no_of_shares": 10, "price": 100},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._accounts_client")
    @patch("transactions.views._holdings_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_invalid_type(
        self, mock_jwks_client, mock_decode, mock_holdings_client, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = TRANSACTION_ACCOUNT

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

    @patch("transactions.views._accounts_client")
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
        mock_accounts_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = TRANSACTION_ACCOUNT
        mock_client.create_transaction.return_value = BUY_TRANSACTION

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "price": 152.5,
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
            no_of_shares=10,
            average_price=None,
            price=152.5,
            date="2026-01-15",
            type="BUY",
        )

    @patch("transactions.views._accounts_client")
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
        mock_accounts_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = TRANSACTION_ACCOUNT
        mock_client.create_transaction.side_effect = InsufficientSharesError("nope")

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "price": 152.5,
                "date": "2026-01-15",
                "type": "SELL",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("transactions.views._accounts_client")
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
        mock_accounts_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = TRANSACTION_ACCOUNT
        mock_client.create_transaction.side_effect = TransactionLimitExceededError("limit")
        mock_client.max_transactions_for_holding = 500

        response = self.client.post(
            reverse("transactions-list"),
            data={
                "holding_id": "h-1",
                "no_of_shares": 10,
                "price": 152.5,
                "date": "2026-01-15",
                "type": "BUY",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("transactions.views._accounts_client")
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
        mock_accounts_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.get_holding.return_value = ACCOUNT_HOLDING
        mock_accounts_client.get_account.return_value = AVERAGE_ACCOUNT
        mock_client.create_transaction.side_effect = TransactionAmountError("bad")

        response = self.client.post(
            reverse("transactions-list"),
            data={"holding_id": "h-1", "no_of_shares": 0, "average_price": 152.5},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)


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

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_an_average_transaction(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
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
            "auth0|abc123", "h-1", "t-1", no_of_shares=15
        )

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_404_for_unknown_transaction(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.update_transaction.side_effect = TransactionNotFoundError("no such transaction")

        response = self.client.patch(
            reverse("transactions-detail", args=["h-1", "missing"]),
            data={"no_of_shares": 15},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 404)

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_400_for_transaction_mode_record(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.update_transaction.side_effect = ValueError("immutable")

        response = self.client.patch(
            reverse("transactions-detail", args=["h-1", "t-2"]),
            data={"no_of_shares": 15},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_400_for_non_positive_amount(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.update_transaction.side_effect = TransactionAmountError("bad")

        response = self.client.patch(
            reverse("transactions-detail", args=["h-1", "t-1"]),
            data={"no_of_shares": 0},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_removes_the_transaction(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.delete(
            reverse("transactions-detail", args=["h-1", "t-1"]), **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_client.delete_transaction.assert_called_once_with("auth0|abc123", "h-1", "t-1")

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
