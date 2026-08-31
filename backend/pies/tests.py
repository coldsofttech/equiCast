from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import (
    AllocationError,
    HoldingAlreadyExistsError,
    HoldingLimitExceededError,
    HoldingNotFoundError,
    PieLimitExceededError,
    PieNotFoundError,
)

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}
PIE = {
    "id": "pie-1",
    "account_id": "acc-1",
    "name": "Core ETFs",
    "description": "Broad market trackers",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class PieListViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("pies-list"))

        self.assertEqual(response.status_code, 401)

    def test_post_without_trailing_slash_returns_404_not_500(self) -> None:
        """Same APPEND_SLASH regression test as accounts/tests.py."""
        response = self.client.post(
            "/api/pies", data={}, content_type="application/json", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 404)

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_users_pies(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_pies.return_value = [PIE]

        response = self.client.get(reverse("pies-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [PIE])
        mock_client.list_pies.assert_called_once_with("auth0|abc123", account_id=None)

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_filters_by_account_id_query_param(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_pies.return_value = [PIE]

        response = self.client.get(reverse("pies-list"), {"account_id": "acc-1"}, **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        mock_client.list_pies.assert_called_once_with("auth0|abc123", account_id="acc-1")

    @patch("pies.views._accounts_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_a_pie(
        self, mock_jwks_client, mock_decode, mock_client, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [{"id": "acc-1"}]
        mock_client.create_pie.return_value = PIE

        create_fields = {
            "name": "Core ETFs",
            "description": "Broad market trackers",
            "account_id": "acc-1",
        }
        response = self.client.post(
            reverse("pies-list"), data=create_fields, content_type="application/json", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), PIE)
        mock_client.create_pie.assert_called_once_with("auth0|abc123", **create_fields)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_a_required_field_is_missing(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("pies-list"),
            data={"name": "Core ETFs"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("pies.views._accounts_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_unknown_or_foreign_account_id(
        self, mock_jwks_client, mock_decode, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [{"id": "some-other-account"}]

        response = self.client.post(
            reverse("pies-list"),
            data={"name": "Core ETFs", "description": "", "account_id": "not-mine"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("pies.views._accounts_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_when_pie_limit_reached(
        self, mock_jwks_client, mock_decode, mock_client, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [{"id": "acc-1"}]
        mock_client.create_pie.side_effect = PieLimitExceededError("limit reached")

        response = self.client.post(
            reverse("pies-list"),
            data={"name": "Core ETFs", "description": "", "account_id": "acc-1"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)


class PieDetailViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("pies-detail", args=["pie-1"]))

        self.assertEqual(response.status_code, 401)

    def test_patch_returns_401_when_unauthenticated(self) -> None:
        response = self.client.patch(reverse("pies-detail", args=["pie-1"]))

        self.assertEqual(response.status_code, 401)

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_pie_with_its_holdings(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE
        holding = {"id": "h-1", "ticker": "VOO", "pie_id": "pie-1"}
        mock_holdings_client.list_holdings.return_value = [holding]

        response = self.client.get(reverse("pies-detail", args=["pie-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {**PIE, "holdings": [holding]})
        mock_client.get_pie.assert_called_once_with("auth0|abc123", "pie-1")
        mock_holdings_client.list_holdings.assert_called_once_with("auth0|abc123", pie_id="pie-1")

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_404_for_unknown_pie(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.side_effect = PieNotFoundError("no such pie")

        response = self.client.get(reverse("pies-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_the_pie(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        updated = {**PIE, "name": "Renamed"}
        mock_client.update_pie.return_value = updated

        response = self.client.patch(
            reverse("pies-detail", args=["pie-1"]),
            data={"name": "Renamed"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), updated)
        mock_client.update_pie.assert_called_once_with("auth0|abc123", "pie-1", name="Renamed")

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_ignores_account_id_since_it_is_immutable(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.update_pie.return_value = PIE

        self.client.patch(
            reverse("pies-detail", args=["pie-1"]),
            data={"name": "Renamed", "account_id": "acc-2"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        mock_client.update_pie.assert_called_once_with("auth0|abc123", "pie-1", name="Renamed")

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_404_for_unknown_pie(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.update_pie.side_effect = PieNotFoundError("no such pie")

        response = self.client.patch(
            reverse("pies-detail", args=["missing"]),
            data={"name": "Renamed"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 404)

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_removes_the_pie_when_it_has_no_holdings(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.list_holdings.return_value = []

        response = self.client.delete(reverse("pies-detail", args=["pie-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 204)
        mock_holdings_client.list_holdings.assert_called_once_with("auth0|abc123", pie_id="pie-1")
        mock_holdings_client.delete_holdings_for_pies.assert_not_called()
        mock_client.delete_pie.assert_called_once_with("auth0|abc123", "pie-1")

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_409_when_pie_has_holdings_and_not_forced(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.list_holdings.return_value = [{"id": "h-1", "pie_id": "pie-1"}]

        response = self.client.delete(reverse("pies-detail", args=["pie-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 409)
        mock_holdings_client.delete_holdings_for_pies.assert_not_called()
        mock_client.delete_pie.assert_not_called()

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_with_force_removes_holdings_then_the_pie(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.list_holdings.return_value = [{"id": "h-1", "pie_id": "pie-1"}]

        response = self.client.delete(
            f"{reverse('pies-detail', args=['pie-1'])}?force=true", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_holdings_client.delete_holdings_for_pies.assert_called_once_with(
            "auth0|abc123", ["pie-1"]
        )
        mock_client.delete_pie.assert_called_once_with("auth0|abc123", "pie-1")

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_404_for_unknown_pie(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.list_holdings.return_value = []
        mock_client.delete_pie.side_effect = PieNotFoundError("no such pie")

        response = self.client.delete(reverse("pies-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)


class PieHoldingsViewTests(TestCase):
    def test_put_returns_401_when_unauthenticated(self) -> None:
        response = self.client.put(reverse("pies-holdings", args=["pie-1"]))

        self.assertEqual(response.status_code, 401)

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_put_returns_404_for_unknown_pie(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.side_effect = PieNotFoundError("no such pie")

        response = self.client.put(
            reverse("pies-holdings", args=["missing"]),
            data={"add": []},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 404)

    @patch("pies.views._market_data_client")
    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_put_adds_holdings_and_returns_the_pie_with_them(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_holdings_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE
        mock_market_data_client.get_profile.return_value = {"ticker": "VOO"}
        new_holding = {"id": "h-1", "ticker": "VOO", "pie_id": "pie-1", "allocation_pct": 100}
        mock_holdings_client.sync_pie_holdings.return_value = [new_holding]

        response = self.client.put(
            reverse("pies-holdings", args=["pie-1"]),
            data={"add": [{"ticker": "voo", "asset_class": "etf", "allocation_pct": 100}]},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {**PIE, "holdings": [new_holding]})
        mock_market_data_client.get_profile.assert_called_once_with("etf", "VOO")
        mock_holdings_client.sync_pie_holdings.assert_called_once_with(
            "auth0|abc123",
            "pie-1",
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
            remove=[],
            reallocate=[],
        )

    @patch("pies.views._market_data_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_put_returns_400_for_unknown_asset_class(
        self, mock_jwks_client, mock_decode, mock_client, mock_market_data_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE

        response = self.client.put(
            reverse("pies-holdings", args=["pie-1"]),
            data={"add": [{"ticker": "VOO", "asset_class": "crypto", "allocation_pct": 100}]},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)
        mock_market_data_client.get_profile.assert_not_called()

    @patch("pies.views._market_data_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_put_returns_400_when_ticker_has_no_market_data(
        self, mock_jwks_client, mock_decode, mock_client, mock_market_data_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE
        mock_market_data_client.get_profile.return_value = None

        response = self.client.put(
            reverse("pies-holdings", args=["pie-1"]),
            data={"add": [{"ticker": "NOPE", "asset_class": "stock", "allocation_pct": 100}]},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_put_returns_400_for_unknown_remove_or_reallocate_id(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE
        mock_holdings_client.sync_pie_holdings.side_effect = HoldingNotFoundError("no such holding")

        response = self.client.put(
            reverse("pies-holdings", args=["pie-1"]),
            data={"remove": ["does-not-exist"]},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_put_returns_409_for_duplicate_ticker(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE
        mock_holdings_client.sync_pie_holdings.side_effect = HoldingAlreadyExistsError("dup")

        response = self.client.put(
            reverse("pies-holdings", args=["pie-1"]),
            data={"remove": [], "reallocate": []},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_put_returns_409_when_pie_holding_limit_reached(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE
        mock_holdings_client.sync_pie_holdings.side_effect = HoldingLimitExceededError("limit")
        mock_holdings_client.max_holdings_for_pie = 50

        response = self.client.put(
            reverse("pies-holdings", args=["pie-1"]),
            data={"remove": [], "reallocate": []},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_put_returns_400_when_allocations_do_not_sum_to_100(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE
        mock_holdings_client.sync_pie_holdings.side_effect = AllocationError("must sum to 100")

        response = self.client.put(
            reverse("pies-holdings", args=["pie-1"]),
            data={"remove": [], "reallocate": []},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("pies.views._holdings_client")
    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_put_removes_and_reallocates_without_touching_market_data(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE
        mock_holdings_client.sync_pie_holdings.return_value = [
            {"id": "h-2", "ticker": "VXUS", "pie_id": "pie-1", "allocation_pct": 100}
        ]

        response = self.client.put(
            reverse("pies-holdings", args=["pie-1"]),
            data={"remove": ["h-1"], "reallocate": [{"id": "h-2", "allocation_pct": 100}]},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        mock_holdings_client.sync_pie_holdings.assert_called_once_with(
            "auth0|abc123",
            "pie-1",
            add=[],
            remove=["h-1"],
            reallocate=[{"id": "h-2", "allocation_pct": 100}],
        )
