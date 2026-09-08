from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import WatchlistLimitExceededError, WatchlistNotFoundError
from watchlists.views import SYSTEM_WATCHLISTS

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}
WATCHLIST = {
    "id": "watch-1",
    "name": "Tech Watch",
    "description": "Big tech names",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class WatchlistListViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("watchlists-list"))

        self.assertEqual(response.status_code, 401)

    def test_post_without_trailing_slash_returns_404_not_500(self) -> None:
        """Same APPEND_SLASH regression test as accounts/tests.py."""
        response = self.client.post(
            "/api/watchlists", data={}, content_type="application/json", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 404)

    @patch("watchlists.views._market_data_client")
    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_system_watchlists_with_empty_holdings_when_nothing_published(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_watchlists.return_value = []
        mock_holdings_client.list_holdings.return_value = []
        mock_market_data_client.get_watchlist_entries.return_value = []

        response = self.client.get(reverse("watchlists-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), [{**w, "type": "system", "holdings": []} for w in SYSTEM_WATCHLISTS]
        )
        mock_market_data_client.get_watchlist_entries.assert_any_call("GLOBAL_MARKETS")
        mock_market_data_client.get_watchlist_entries.assert_any_call("TOP_WINNERS")
        mock_market_data_client.get_watchlist_entries.assert_any_call("TOP_LOSERS")
        self.assertEqual(mock_market_data_client.get_watchlist_entries.call_count, 3)

    @patch("watchlists.views._market_data_client")
    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_populates_global_markets_from_the_published_watchlist_entries(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_watchlists.return_value = []
        mock_holdings_client.list_holdings.return_value = []
        entry = {
            "watchlist_key": "GLOBAL_MARKETS",
            "asset_class": "future",
            "ticker": "GOLD",
            "symbol": "GC=F",
            "name": "Gold",
            "currency": "USD",
            "current_price": 2440.3,
            "change_1w_pct": 1.2,
            "change_1m_pct": -0.4,
            "last_updated": "2026-08-28T21:29:05+00:00",
            "source": "yfinance",
        }
        mock_market_data_client.get_watchlist_entries.side_effect = (
            lambda key: [entry] if key == "GLOBAL_MARKETS" else []
        )

        response = self.client.get(reverse("watchlists-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        global_markets = next(w for w in body if w["id"] == "global-markets")
        self.assertEqual(global_markets["holdings"], [entry])
        # Top Winners/Top Losers have a storage key mapped too (they just
        # weren't published under it in this test), but the "(Your
        # Accounts)" watchlists have no storage key at all, so neither ever
        # calls get_watchlist_entries.
        no_storage_key = [
            w for w in body if w["type"] == "system" and w["id"].endswith("-accounts")
        ]
        self.assertTrue(all(w["holdings"] == [] for w in no_storage_key))
        mock_market_data_client.get_watchlist_entries.assert_any_call("GLOBAL_MARKETS")
        mock_market_data_client.get_watchlist_entries.assert_any_call("TOP_WINNERS")
        mock_market_data_client.get_watchlist_entries.assert_any_call("TOP_LOSERS")

    @patch("watchlists.views._market_data_client")
    @patch("watchlists.views._profile_client")
    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_nests_and_enriches_each_custom_watchlists_holdings(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_holdings_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_watchlists.return_value = [WATCHLIST]
        holding = {"id": "h-1", "ticker": "AAPL", "asset_class": "stock", "watchlist_id": "watch-1"}
        other_holding = {
            "id": "h-2", "ticker": "VXUS", "asset_class": "etf", "watchlist_id": "not-this-user-list"
        }
        mock_holdings_client.list_holdings.return_value = [holding, other_holding]
        mock_profile_client.get_or_create_profile.return_value = {"default_currency": "USD"}
        enriched_holding = {
            **holding,
            "name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "website": "https://www.apple.com",
            "current_price_native": 200.0,
            "current_price": 200.0,
        }
        mock_market_data_client.enrich_holdings.return_value = [enriched_holding]
        mock_market_data_client.get_watchlist_entries.return_value = []

        response = self.client.get(reverse("watchlists-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), len(SYSTEM_WATCHLISTS) + 1)
        self.assertEqual(body[-1], {**WATCHLIST, "type": "custom", "holdings": [enriched_holding]})
        # Only watch-1's own holding is passed through — other_holding
        # belongs to a watchlist_id outside this caller's watchlist list,
        # filtered out before enrichment (see WatchlistListView.get).
        mock_market_data_client.enrich_holdings.assert_called_once_with([holding], "USD")

    @patch("watchlists.views._market_data_client")
    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_system_watchlists_before_custom_ones(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client, mock_market_data_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_watchlists.return_value = [WATCHLIST]
        mock_holdings_client.list_holdings.return_value = []
        mock_market_data_client.get_watchlist_entries.return_value = []

        response = self.client.get(reverse("watchlists-list"), **AUTH_HEADER)

        body = response.json()
        self.assertEqual([w["id"] for w in body[: len(SYSTEM_WATCHLISTS)]], [w["id"] for w in SYSTEM_WATCHLISTS])
        self.assertEqual(body[-1]["id"], "watch-1")

    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_a_watchlist(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.create_watchlist.return_value = WATCHLIST

        create_fields = {"name": "Tech Watch", "description": "Big tech names"}
        response = self.client.post(
            reverse("watchlists-list"),
            data=create_fields,
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {**WATCHLIST, "type": "custom", "holdings": []})
        mock_client.create_watchlist.assert_called_once_with("auth0|abc123", **create_fields)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_a_required_field_is_missing(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("watchlists-list"),
            data={"name": "Tech Watch"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_when_watchlist_limit_reached(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.create_watchlist.side_effect = WatchlistLimitExceededError("limit reached")

        response = self.client.post(
            reverse("watchlists-list"),
            data={"name": "Tech Watch", "description": ""},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)


class WatchlistDetailViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("watchlists-detail", args=["watch-1"]))

        self.assertEqual(response.status_code, 401)

    def test_patch_returns_401_when_unauthenticated(self) -> None:
        response = self.client.patch(reverse("watchlists-detail", args=["watch-1"]))

        self.assertEqual(response.status_code, 401)

    @patch("watchlists.views._market_data_client")
    @patch("watchlists.views._profile_client")
    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_watchlist_with_its_enriched_holdings(
        self,
        mock_jwks_client,
        mock_decode,
        mock_client,
        mock_holdings_client,
        mock_profile_client,
        mock_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_watchlist.return_value = WATCHLIST
        holding = {"id": "h-1", "ticker": "AAPL", "asset_class": "stock", "watchlist_id": "watch-1"}
        mock_holdings_client.list_holdings.return_value = [holding]
        mock_profile_client.get_or_create_profile.return_value = {"default_currency": "USD"}
        enriched_holding = {**holding, "name": "Apple Inc.", "current_price": 200.0}
        mock_market_data_client.enrich_holdings.return_value = [enriched_holding]

        response = self.client.get(reverse("watchlists-detail", args=["watch-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {**WATCHLIST, "type": "custom", "holdings": [enriched_holding]}
        )
        mock_client.get_watchlist.assert_called_once_with("auth0|abc123", "watch-1")
        mock_holdings_client.list_holdings.assert_called_once_with(
            "auth0|abc123", watchlist_id="watch-1"
        )
        mock_market_data_client.enrich_holdings.assert_called_once_with([holding], "USD")

    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_404_for_unknown_watchlist(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_watchlist.side_effect = WatchlistNotFoundError("no such watchlist")

        response = self.client.get(reverse("watchlists-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)

    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_the_watchlist(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        updated = {**WATCHLIST, "name": "Renamed"}
        mock_client.update_watchlist.return_value = updated

        response = self.client.patch(
            reverse("watchlists-detail", args=["watch-1"]),
            data={"name": "Renamed"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {**updated, "type": "custom"})
        mock_client.update_watchlist.assert_called_once_with(
            "auth0|abc123", "watch-1", name="Renamed"
        )

    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_404_for_unknown_watchlist(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.update_watchlist.side_effect = WatchlistNotFoundError("no such watchlist")

        response = self.client.patch(
            reverse("watchlists-detail", args=["missing"]),
            data={"name": "Renamed"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 404)

    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_removes_the_watchlist_when_it_has_no_holdings(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.list_holdings.return_value = []

        response = self.client.delete(reverse("watchlists-detail", args=["watch-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 204)
        mock_holdings_client.list_holdings.assert_called_once_with(
            "auth0|abc123", watchlist_id="watch-1"
        )
        mock_holdings_client.delete_holdings_for_watchlist.assert_not_called()
        mock_client.delete_watchlist.assert_called_once_with("auth0|abc123", "watch-1")

    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_409_when_watchlist_has_holdings_and_not_forced(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.list_holdings.return_value = [{"id": "h-1", "watchlist_id": "watch-1"}]

        response = self.client.delete(reverse("watchlists-detail", args=["watch-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 409)
        mock_holdings_client.delete_holdings_for_watchlist.assert_not_called()
        mock_client.delete_watchlist.assert_not_called()

    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_with_force_removes_holdings_then_the_watchlist(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.list_holdings.return_value = [{"id": "h-1", "watchlist_id": "watch-1"}]

        response = self.client.delete(
            f"{reverse('watchlists-detail', args=['watch-1'])}?force=true", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_holdings_client.delete_holdings_for_watchlist.assert_called_once_with(
            "auth0|abc123", "watch-1"
        )
        mock_client.delete_watchlist.assert_called_once_with("auth0|abc123", "watch-1")

    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_with_force_and_no_holdings_skips_the_bulk_delete(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.list_holdings.return_value = []

        response = self.client.delete(
            f"{reverse('watchlists-detail', args=['watch-1'])}?force=true", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_holdings_client.delete_holdings_for_watchlist.assert_not_called()
        mock_client.delete_watchlist.assert_called_once_with("auth0|abc123", "watch-1")

    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_404_for_unknown_watchlist(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_holdings_client.list_holdings.return_value = []
        mock_client.delete_watchlist.side_effect = WatchlistNotFoundError("no such watchlist")

        response = self.client.delete(reverse("watchlists-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)
