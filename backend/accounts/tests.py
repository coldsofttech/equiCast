from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import AccountAlreadyExistsError, AccountLimitExceededError, AccountNotFoundError

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}
ACCOUNT = {
    "id": "acc-1",
    "name": "ISA",
    "description": "Stocks & shares ISA",
    "account_type": "ISA",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class AccountListViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("accounts-list"))

        self.assertEqual(response.status_code, 401)

    def test_post_without_trailing_slash_returns_404_not_500(self) -> None:
        """Regression test for APPEND_SLASH: CommonMiddleware refuses to
        redirect a POST missing its trailing slash (redirecting risks
        dropping the body) and raises RuntimeError instead, which — with
        Django's default APPEND_SLASH=True — surfaces as an unhandled 500.
        APPEND_SLASH=False (settings.py) makes this a plain 404 instead,
        for every HTTP method."""
        response = self.client.post(
            "/api/accounts", data={}, content_type="application/json", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 404)

    @patch("accounts.views._market_data_client")
    @patch("accounts.views._profile_client")
    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_users_accounts_bare_when_nothing_nested(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_pies_client,
        mock_holdings_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_accounts.return_value = [ACCOUNT]
        mock_pies_client.list_pies.return_value = []
        mock_holdings_client.list_holdings.return_value = []

        response = self.client.get(reverse("accounts-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{**ACCOUNT, "pies": [], "holdings": []}])
        mock_client.list_accounts.assert_called_once_with("auth0|abc123")
        mock_pies_client.list_pies.assert_called_once_with("auth0|abc123")
        mock_holdings_client.list_holdings.assert_called_once_with("auth0|abc123")
        # No holdings to enrich — profile/market-data lookups are skipped
        # entirely (see accounts.views._enrich_holdings's short-circuit).
        mock_profile_client.get_or_create_profile.assert_not_called()
        mock_market_data_client.enrich_holdings.assert_not_called()

    @patch("accounts.views._market_data_client")
    @patch("accounts.views._profile_client")
    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_nests_pies_with_their_holdings_and_direct_account_holdings(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_pies_client,
        mock_holdings_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        pie = {"id": "pie-1", "account_id": "acc-1", "name": "Core ETFs"}
        pie_holding = {
            "id": "h-1",
            "ticker": "VOO",
            "asset_class": "etf",
            "pie_id": "pie-1",
            "account_id": None,
        }
        direct_holding = {
            "id": "h-2",
            "ticker": "AAPL",
            "asset_class": "stock",
            "pie_id": None,
            "account_id": "acc-1",
        }
        enriched_pie_holding = {
            **pie_holding, "current_price_native": 450.0, "current_price": 450.0
        }
        enriched_direct_holding = {
            **direct_holding, "current_price_native": 190.0, "current_price": 190.0
        }
        mock_client.list_accounts.return_value = [ACCOUNT]
        mock_pies_client.list_pies.return_value = [pie]
        mock_holdings_client.list_holdings.return_value = [pie_holding, direct_holding]
        # TRANSACTION mode so sync_dividends_for_holdings (GitHub issue
        # #123) is a no-op here — see SyncDividendsForHoldingsTests
        # (transactions/tests.py) for that sync's own coverage.
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "TRANSACTION",
            "default_currency": "GBP",
        }
        # Enrichment itself (catalog lookup/FX conversion) is unit-tested at
        # MarketDataClient.enrich_holdings — this only checks the flat
        # enriched list is threaded through and split back into
        # pies/direct holdings correctly (see _nest_pies_and_holdings).
        mock_market_data_client.enrich_holdings.return_value = [
            enriched_pie_holding,
            enriched_direct_holding,
        ]

        response = self.client.get(reverse("accounts-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    **ACCOUNT,
                    "pies": [{**pie, "holdings": [enriched_pie_holding]}],
                    "holdings": [enriched_direct_holding],
                }
            ],
        )
        mock_market_data_client.enrich_holdings.assert_called_once_with(
            [pie_holding, direct_holding], "GBP"
        )

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_an_account(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.create_account.return_value = ACCOUNT

        create_fields = {
            "name": "ISA",
            "description": "Stocks & shares ISA",
            "account_type": "ISA",
        }
        response = self.client.post(
            reverse("accounts-list"),
            data=create_fields,
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), ACCOUNT)
        mock_client.create_account.assert_called_once_with("auth0|abc123", **create_fields)

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_passes_icon_through_when_given(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.create_account.return_value = {**ACCOUNT, "icon": "bank2"}

        create_fields = {
            "name": "ISA",
            "description": "Stocks & shares ISA",
            "account_type": "ISA",
            "icon": "bank2",
        }
        response = self.client.post(
            reverse("accounts-list"),
            data=create_fields,
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        mock_client.create_account.assert_called_once_with("auth0|abc123", **create_fields)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_a_required_field_is_missing(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("accounts-list"),
            data={"name": "ISA"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_when_account_limit_reached(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.create_account.side_effect = AccountLimitExceededError("limit reached")

        response = self.client.post(
            reverse("accounts-list"),
            data={
                "name": "ISA",
                "description": "",
                "account_type": "ISA",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_when_account_name_already_exists(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.create_account.side_effect = AccountAlreadyExistsError("duplicate name")

        response = self.client.post(
            reverse("accounts-list"),
            data={
                "name": "Stocks & shares ISA",
                "description": "",
                "account_type": "ISA",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)


class AccountDetailViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("accounts-detail", args=["acc-1"]))

        self.assertEqual(response.status_code, 401)

    def test_patch_returns_401_when_unauthenticated(self) -> None:
        response = self.client.patch(reverse("accounts-detail", args=["acc-1"]))

        self.assertEqual(response.status_code, 401)

    @patch("accounts.views._market_data_client")
    @patch("accounts.views._profile_client")
    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_account_with_its_pies_and_holdings(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_pies_client,
        mock_holdings_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_account.return_value = ACCOUNT
        pie = {"id": "pie-1", "account_id": "acc-1", "name": "Core ETFs"}
        pie_holding = {
            "id": "h-1",
            "ticker": "VOO",
            "asset_class": "etf",
            "pie_id": "pie-1",
            "account_id": None,
        }
        direct_holding = {
            "id": "h-2",
            "ticker": "AAPL",
            "asset_class": "stock",
            "pie_id": None,
            "account_id": "acc-1",
        }
        enriched_pie_holding = {
            **pie_holding, "current_price_native": 450.0, "current_price": 450.0
        }
        enriched_direct_holding = {
            **direct_holding, "current_price_native": 190.0, "current_price": 190.0
        }
        mock_pies_client.list_pies.return_value = [pie]
        mock_holdings_client.list_holdings.return_value = [pie_holding, direct_holding]
        # TRANSACTION mode so sync_dividends_for_holdings (GitHub issue
        # #123) is a no-op here — see SyncDividendsForHoldingsTests
        # (transactions/tests.py) for that sync's own coverage.
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "TRANSACTION",
            "default_currency": "GBP",
        }
        mock_market_data_client.enrich_holdings.return_value = [
            enriched_pie_holding,
            enriched_direct_holding,
        ]

        response = self.client.get(reverse("accounts-detail", args=["acc-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                **ACCOUNT,
                "pies": [{**pie, "holdings": [enriched_pie_holding]}],
                "holdings": [enriched_direct_holding],
            },
        )
        mock_client.get_account.assert_called_once_with("auth0|abc123", "acc-1")
        mock_pies_client.list_pies.assert_called_once_with("auth0|abc123", account_id="acc-1")
        mock_holdings_client.list_holdings.assert_called_once_with("auth0|abc123")
        mock_market_data_client.enrich_holdings.assert_called_once_with(
            [pie_holding, direct_holding], "GBP"
        )

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_404_for_unknown_account(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_account.side_effect = AccountNotFoundError("no such account")

        response = self.client.get(reverse("accounts-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_the_account(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        updated = {**ACCOUNT, "name": "Renamed"}
        mock_client.update_account.return_value = updated

        response = self.client.patch(
            reverse("accounts-detail", args=["acc-1"]),
            data={"name": "Renamed"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), updated)
        mock_client.update_account.assert_called_once_with("auth0|abc123", "acc-1", name="Renamed")

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_the_icon(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        updated = {**ACCOUNT, "icon": "bank2"}
        mock_client.update_account.return_value = updated

        response = self.client.patch(
            reverse("accounts-detail", args=["acc-1"]),
            data={"icon": "bank2"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        mock_client.update_account.assert_called_once_with("auth0|abc123", "acc-1", icon="bank2")

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_404_for_unknown_account(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.update_account.side_effect = AccountNotFoundError("no such account")

        response = self.client.patch(
            reverse("accounts-detail", args=["missing"]),
            data={"name": "Renamed"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 404)

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_409_when_account_name_already_exists(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.update_account.side_effect = AccountAlreadyExistsError("duplicate name")

        response = self.client.patch(
            reverse("accounts-detail", args=["acc-1"]),
            data={"name": "Stocks & shares ISA"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_removes_the_account_when_it_has_no_pies_or_holdings(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = []
        mock_holdings_client.list_holdings.return_value = []

        response = self.client.delete(reverse("accounts-detail", args=["acc-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 204)
        mock_pies_client.list_pies.assert_called_once_with("auth0|abc123", account_id="acc-1")
        mock_holdings_client.list_holdings.assert_called_once_with(
            "auth0|abc123", account_id="acc-1"
        )
        mock_pies_client.delete_pies_for_account.assert_not_called()
        mock_holdings_client.delete_holdings_for_pies.assert_not_called()
        mock_holdings_client.delete_holdings_for_account.assert_not_called()
        mock_client.delete_account.assert_called_once_with("auth0|abc123", "acc-1")

    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_409_when_account_has_pies_and_not_forced(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = [{"id": "pie-1", "account_id": "acc-1"}]
        mock_holdings_client.list_holdings.return_value = []

        response = self.client.delete(reverse("accounts-detail", args=["acc-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 409)
        mock_pies_client.delete_pies_for_account.assert_not_called()
        mock_client.delete_account.assert_not_called()

    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_409_when_account_has_direct_holdings_and_not_forced(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = []
        mock_holdings_client.list_holdings.return_value = [{"id": "h-1", "account_id": "acc-1"}]

        response = self.client.delete(reverse("accounts-detail", args=["acc-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 409)
        mock_holdings_client.delete_holdings_for_account.assert_not_called()
        mock_client.delete_account.assert_not_called()

    @patch("accounts.views._transactions_client")
    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_with_force_removes_pies_and_their_holdings_then_the_account(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_pies_client,
        mock_holdings_client,
        mock_transactions_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = [{"id": "pie-1", "account_id": "acc-1"}]

        def list_holdings(user_id, account_id=None):
            if account_id is not None:
                return []
            return [{"id": "h-1", "account_id": None, "pie_id": "pie-1"}]

        mock_holdings_client.list_holdings.side_effect = list_holdings

        response = self.client.delete(
            f"{reverse('accounts-detail', args=['acc-1'])}?force=true", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_transactions_client.delete_transactions_for_holdings.assert_called_once_with(
            "auth0|abc123", ["h-1"]
        )
        mock_holdings_client.delete_holdings_for_pies.assert_called_once_with(
            "auth0|abc123", ["pie-1"]
        )
        mock_pies_client.delete_pies_for_account.assert_called_once_with("auth0|abc123", "acc-1")
        mock_holdings_client.delete_holdings_for_account.assert_not_called()
        mock_client.delete_account.assert_called_once_with("auth0|abc123", "acc-1")

    @patch("accounts.views._transactions_client")
    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_with_force_removes_direct_holdings_then_the_account(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_pies_client,
        mock_holdings_client,
        mock_transactions_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = []
        mock_holdings_client.list_holdings.return_value = [{"id": "h-1", "account_id": "acc-1"}]

        response = self.client.delete(
            f"{reverse('accounts-detail', args=['acc-1'])}?force=true", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_pies_client.delete_pies_for_account.assert_not_called()
        mock_transactions_client.delete_transactions_for_holdings.assert_called_once_with(
            "auth0|abc123", ["h-1"]
        )
        mock_holdings_client.delete_holdings_for_account.assert_called_once_with(
            "auth0|abc123", "acc-1"
        )
        mock_client.delete_account.assert_called_once_with("auth0|abc123", "acc-1")

    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_with_force_and_nothing_nested_skips_the_bulk_deletes(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = []
        mock_holdings_client.list_holdings.return_value = []

        response = self.client.delete(
            f"{reverse('accounts-detail', args=['acc-1'])}?force=true", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_pies_client.delete_pies_for_account.assert_not_called()
        mock_holdings_client.delete_holdings_for_pies.assert_not_called()
        mock_holdings_client.delete_holdings_for_account.assert_not_called()
        mock_client.delete_account.assert_called_once_with("auth0|abc123", "acc-1")

    @patch("accounts.views._holdings_client")
    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_404_for_unknown_account(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = []
        mock_holdings_client.list_holdings.return_value = []
        mock_client.delete_account.side_effect = AccountNotFoundError("no such account")

        response = self.client.delete(reverse("accounts-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)
