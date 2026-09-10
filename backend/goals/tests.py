from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse
from equicast_core import GoalLimitExceededError, GoalMappingConflictError, GoalNotFoundError

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}
GOAL = {
    "id": "goal-1",
    "name": "House deposit",
    "purpose": "buy_home",
    "custom_purpose": None,
    "target_amount": 20000,
    "target_date": None,
    "account_ids": ["acc-1"],
    "pie_ids": [],
    "status": "active",
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}
ACCOUNT = {"id": "acc-1", "name": "ISA"}
PIE = {"id": "pie-1", "account_id": "acc-1", "name": "Growth"}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class GoalListViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("goals-list"))

        self.assertEqual(response.status_code, 401)

    def test_post_without_trailing_slash_returns_404_not_500(self) -> None:
        """Same APPEND_SLASH regression test as accounts/tests.py."""
        response = self.client.post(
            "/api/goals", data={}, content_type="application/json", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 404)

    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_users_goals(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.list_goals.return_value = [GOAL]

        response = self.client.get(reverse("goals-list"), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [GOAL])
        mock_client.list_goals.assert_called_once_with("auth0|abc123")

    @patch("goals.views._pies_client")
    @patch("goals.views._accounts_client")
    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_a_goal(
        self, mock_jwks_client, mock_decode, mock_client, mock_accounts_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [ACCOUNT]
        mock_pies_client.list_pies.return_value = []
        mock_client.create_goal.return_value = GOAL

        create_fields = {
            "name": "House deposit",
            "purpose": "buy_home",
            "target_amount": 20000,
            "account_ids": ["acc-1"],
        }
        response = self.client.post(
            reverse("goals-list"), data=create_fields, content_type="application/json", **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), GOAL)
        mock_client.create_goal.assert_called_once_with(
            "auth0|abc123",
            name="House deposit",
            purpose="buy_home",
            target_amount=20000,
            account_ids=["acc-1"],
        )

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_a_required_field_is_missing(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("goals-list"),
            data={"name": "House deposit"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_unknown_purpose(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("goals-list"),
            data={"name": "House deposit", "purpose": "yacht", "target_amount": 20000},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_other_purpose_has_no_custom_purpose(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("goals-list"),
            data={"name": "Misc", "purpose": "other", "target_amount": 1000},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("goals.views._accounts_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_unknown_account_id(
        self, mock_jwks_client, mock_decode, mock_accounts_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = []

        response = self.client.post(
            reverse("goals-list"),
            data={
                "name": "House deposit",
                "purpose": "buy_home",
                "target_amount": 20000,
                "account_ids": ["missing"],
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("goals.views._pies_client")
    @patch("goals.views._accounts_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_pies_own_account_is_also_mapped(
        self, mock_jwks_client, mock_decode, mock_accounts_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [ACCOUNT]
        mock_pies_client.list_pies.return_value = [PIE]

        response = self.client.post(
            reverse("goals-list"),
            data={
                "name": "House deposit",
                "purpose": "buy_home",
                "target_amount": 20000,
                "account_ids": ["acc-1"],
                "pie_ids": ["pie-1"],
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("goals.views._pies_client")
    @patch("goals.views._accounts_client")
    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_when_goal_limit_reached(
        self, mock_jwks_client, mock_decode, mock_client, mock_accounts_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = []
        mock_pies_client.list_pies.return_value = []
        mock_client.create_goal.side_effect = GoalLimitExceededError("limit reached")

        response = self.client.post(
            reverse("goals-list"),
            data={"name": "House deposit", "purpose": "buy_home", "target_amount": 20000},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)

    @patch("goals.views._pies_client")
    @patch("goals.views._accounts_client")
    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_409_when_mapping_conflicts(
        self, mock_jwks_client, mock_decode, mock_client, mock_accounts_client, mock_pies_client
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_accounts_client.list_accounts.return_value = [ACCOUNT]
        mock_pies_client.list_pies.return_value = []
        mock_client.create_goal.side_effect = GoalMappingConflictError("already mapped")

        response = self.client.post(
            reverse("goals-list"),
            data={
                "name": "House deposit",
                "purpose": "buy_home",
                "target_amount": 20000,
                "account_ids": ["acc-1"],
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 409)


class GoalDetailViewTests(TestCase):
    def test_get_returns_401_when_unauthenticated(self) -> None:
        response = self.client.get(reverse("goals-detail", args=["goal-1"]))

        self.assertEqual(response.status_code, 401)

    def test_patch_returns_401_when_unauthenticated(self) -> None:
        response = self.client.patch(reverse("goals-detail", args=["goal-1"]))

        self.assertEqual(response.status_code, 401)

    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_the_goal(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_goal.return_value = GOAL

        response = self.client.get(reverse("goals-detail", args=["goal-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), GOAL)
        mock_client.get_goal.assert_called_once_with("auth0|abc123", "goal-1")

    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_get_returns_404_for_unknown_goal(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.get_goal.side_effect = GoalNotFoundError("no such goal")

        response = self.client.get(reverse("goals-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)

    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_updates_the_goal(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        updated = {**GOAL, "status": "achieved"}
        mock_client.update_goal.return_value = updated

        response = self.client.patch(
            reverse("goals-detail", args=["goal-1"]),
            data={"status": "achieved"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), updated)
        mock_client.update_goal.assert_called_once_with("auth0|abc123", "goal-1", status="achieved")

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_400_for_unknown_status(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.patch(
            reverse("goals-detail", args=["goal-1"]),
            data={"status": "cancelled"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_patch_returns_404_for_unknown_goal(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.update_goal.side_effect = GoalNotFoundError("no such goal")

        response = self.client.patch(
            reverse("goals-detail", args=["missing"]),
            data={"name": "Renamed"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 404)

    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_removes_the_goal(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.delete(reverse("goals-detail", args=["goal-1"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 204)
        mock_client.delete_goal.assert_called_once_with("auth0|abc123", "goal-1")

    @patch("goals.views._client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_delete_returns_404_for_unknown_goal(self, mock_jwks_client, mock_decode, mock_client) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_client.delete_goal.side_effect = GoalNotFoundError("no such goal")

        response = self.client.delete(reverse("goals-detail", args=["missing"]), **AUTH_HEADER)

        self.assertEqual(response.status_code, 404)
