from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import AccountLimitExceededError, AccountNotFoundError

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}
ACCOUNT = {
    "id": "acc-1",
    "name": "ISA",
    "description": "Stocks & shares ISA",
    "account_type": "ISA",
    "currency": "GBP",
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

    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_users_accounts(
        self, mock_jwks_client, mock_decode, mock_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_accounts.return_value = [ACCOUNT]

        response = self.client.get(reverse("accounts-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [ACCOUNT])
        mock_client.list_accounts.assert_called_once_with("auth0|abc123")

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
            "currency": "GBP",
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
            data={"name": "ISA", "description": "", "account_type": "ISA", "currency": "GBP"},
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

    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_account_with_its_pies(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_account.return_value = ACCOUNT
        pie = {"id": "pie-1", "account_id": "acc-1", "name": "Core ETFs"}
        mock_pies_client.list_pies.return_value = [pie]

        response = self.client.get(reverse("accounts-detail", args=["acc-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {**ACCOUNT, "pies": [pie]})
        mock_client.get_account.assert_called_once_with("auth0|abc123", "acc-1")
        mock_pies_client.list_pies.assert_called_once_with("auth0|abc123", account_id="acc-1")

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

    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_removes_the_account_when_it_has_no_pies(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = []

        response = self.client.delete(reverse("accounts-detail", args=["acc-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 204)
        mock_pies_client.list_pies.assert_called_once_with("auth0|abc123", account_id="acc-1")
        mock_pies_client.delete_pies_for_account.assert_not_called()
        mock_client.delete_account.assert_called_once_with("auth0|abc123", "acc-1")

    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_409_when_account_has_pies_and_not_forced(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = [{"id": "pie-1", "account_id": "acc-1"}]

        response = self.client.delete(reverse("accounts-detail", args=["acc-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 409)
        mock_pies_client.delete_pies_for_account.assert_not_called()
        mock_client.delete_account.assert_not_called()

    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_with_force_removes_pies_then_the_account(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = [{"id": "pie-1", "account_id": "acc-1"}]

        response = self.client.delete(
            f"{reverse('accounts-detail', args=['acc-1'])}?force=true", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_pies_client.delete_pies_for_account.assert_called_once_with("auth0|abc123", "acc-1")
        mock_client.delete_account.assert_called_once_with("auth0|abc123", "acc-1")

    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_with_force_and_no_pies_skips_the_bulk_delete(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = []

        response = self.client.delete(
            f"{reverse('accounts-detail', args=['acc-1'])}?force=true", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 204)
        mock_pies_client.delete_pies_for_account.assert_not_called()
        mock_client.delete_account.assert_called_once_with("auth0|abc123", "acc-1")

    @patch("accounts.views._pies_client")
    @patch("accounts.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_404_for_unknown_account(
        self, mock_jwks_client, mock_decode, mock_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_pies_client.list_pies.return_value = []
        mock_client.delete_account.side_effect = AccountNotFoundError("no such account")

        response = self.client.delete(reverse("accounts-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)
