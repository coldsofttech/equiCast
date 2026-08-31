from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import PieLimitExceededError, PieNotFoundError

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

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_pie(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_pie.return_value = PIE

        response = self.client.get(reverse("pies-detail", args=["pie-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), PIE)
        mock_client.get_pie.assert_called_once_with("auth0|abc123", "pie-1")

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

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_removes_the_pie(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.delete(reverse("pies-detail", args=["pie-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 204)
        mock_client.delete_pie.assert_called_once_with("auth0|abc123", "pie-1")

    @patch("pies.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_404_for_unknown_pie(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.delete_pie.side_effect = PieNotFoundError("no such pie")

        response = self.client.delete(reverse("pies-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)
