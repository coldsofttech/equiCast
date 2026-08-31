from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import WatchlistLimitExceededError, WatchlistNotFoundError

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

    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_users_watchlists(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_watchlists.return_value = [WATCHLIST]

        response = self.client.get(reverse("watchlists-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [WATCHLIST])
        mock_client.list_watchlists.assert_called_once_with("auth0|abc123")

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
        self.assertEqual(response.json(), WATCHLIST)
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

    @patch("watchlists.views._holdings_client")
    @patch("watchlists.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_watchlist_with_its_holdings(
        self, mock_jwks_client, mock_decode, mock_client, mock_holdings_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_watchlist.return_value = WATCHLIST
        holding = {"id": "h-1", "ticker": "AAPL", "watchlist_id": "watch-1"}
        mock_holdings_client.list_holdings.return_value = [holding]

        response = self.client.get(reverse("watchlists-detail", args=["watch-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {**WATCHLIST, "holdings": [holding]})
        mock_client.get_watchlist.assert_called_once_with("auth0|abc123", "watch-1")
        mock_holdings_client.list_holdings.assert_called_once_with(
            "auth0|abc123", watchlist_id="watch-1"
        )

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
        self.assertEqual(response.json(), updated)
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
