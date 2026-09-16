from unittest.mock import MagicMock, patch
from urllib.error import URLError

from django.test import TestCase
from django.urls import reverse

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class SupportViewTests(TestCase):
    def test_post_returns_401_when_unauthenticated(self) -> None:
        response = self.client.post(
            reverse("support"),
            data={"category": "query", "description": "How do I add a holding?"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    @patch("support.views._create_github_issue")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_issue_and_returns_generic_confirmation(
        self, mock_jwks_client, mock_decode, mock_create_issue
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={
                "category": "ticker-request",
                "description": "Please add NVDA.",
                "ticker": "NVDA",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"detail": "Thanks — we've received this."})
        mock_create_issue.assert_called_once()
        title, body, labels = mock_create_issue.call_args[0]
        self.assertIn("Please add NVDA.", title)
        self.assertIn("**Ticker:** NVDA", body)
        self.assertIn("**Submitted by (user_id):** auth0|abc123", body)
        self.assertEqual(labels, ["ticker-request", "development"])

    @patch("support.views._create_github_issue")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_omits_ticker_line_when_not_given(
        self, mock_jwks_client, mock_decode, mock_create_issue
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={"category": "query", "description": "How do I add a holding?"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        _title, body, _labels = mock_create_issue.call_args[0]
        self.assertNotIn("**Ticker:**", body)

    @patch("support.views._create_github_issue")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_maps_environment_name_to_its_github_label(
        self, mock_jwks_client, mock_decode, mock_create_issue
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        with self.settings(ENVIRONMENT_NAME="prod"):
            response = self.client.post(
                reverse("support"),
                data={"category": "other", "description": "hello"},
                content_type="application/json",
                **AUTH_HEADER,
            )

        self.assertEqual(response.status_code, 201)
        _title, _body, labels = mock_create_issue.call_args[0]
        self.assertEqual(labels, ["customer-other", "production"])

    @patch("support.views._create_github_issue")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_maps_query_category_to_its_github_label(
        self, mock_jwks_client, mock_decode, mock_create_issue
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={"category": "query", "description": "How do I add a holding?"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        _title, _body, labels = mock_create_issue.call_args[0]
        self.assertEqual(labels, ["customer-query", "development"])

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_rejects_unknown_category(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={"category": "bogus", "description": "hello"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_rejects_blank_description(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={"category": "query", "description": "   "},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_rejects_ticker_request_without_a_ticker(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={"category": "ticker-request", "description": "Please add NVDA."},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("support.views._create_github_issue")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_accepts_ticker_request_without_a_description(
        self, mock_jwks_client, mock_decode, mock_create_issue
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={"category": "ticker-request", "ticker": "NVDA"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        title, body, _labels = mock_create_issue.call_args[0]
        self.assertIn("NVDA", title)
        self.assertIn("**Ticker:** NVDA", body)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_rejects_incorrect_data_without_a_subject_type(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={
                "category": "incorrect-data",
                "description": "The value looks wrong.",
                "subject": "My ISA",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_rejects_incorrect_data_without_a_subject(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={
                "category": "incorrect-data",
                "description": "The value looks wrong.",
                "subject_type": "account",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_rejects_incorrect_data_without_a_description(
        self, mock_jwks_client, mock_decode
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={"category": "incorrect-data", "subject_type": "account", "subject": "My ISA"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("support.views._create_github_issue")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_creates_incorrect_data_issue_with_subject(
        self, mock_jwks_client, mock_decode, mock_create_issue
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={
                "category": "incorrect-data",
                "description": "The invested amount looks wrong.",
                "subject_type": "pie",
                "subject": "Growth Pie",
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 201)
        title, body, labels = mock_create_issue.call_args[0]
        self.assertIn("[Incorrect Data]", title)
        self.assertIn("**Affected Pie:** Growth Pie", body)
        self.assertEqual(labels, ["customer-issue", "development"])

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_rejects_description_over_max_length(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={"category": "query", "description": "x" * 4001},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_rejects_ticker_over_max_length(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("support"),
            data={"category": "ticker-request", "description": "add it", "ticker": "X" * 16},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("support.views._create_github_issue")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_502_when_github_call_fails(
        self, mock_jwks_client, mock_decode, mock_create_issue
    ) -> None:
        from support.views import GitHubIssueError

        _authenticate(mock_jwks_client, mock_decode)
        mock_create_issue.side_effect = GitHubIssueError("boom")

        response = self.client.post(
            reverse("support"),
            data={"category": "other", "description": "hello"},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 502)


class CreateGitHubIssueTests(TestCase):
    def test_raises_when_token_not_configured(self) -> None:
        from support.views import GitHubIssueError, _create_github_issue

        with self.settings(SUPPORT_ISSUE_TOKEN=None):
            with self.assertRaises(GitHubIssueError):
                _create_github_issue("title", "body", ["query"])

    @patch("support.views.urllib.request.urlopen")
    def test_raises_on_network_error(self, mock_urlopen) -> None:
        from support.views import GitHubIssueError, _create_github_issue

        mock_urlopen.side_effect = URLError("no network")

        with self.settings(SUPPORT_ISSUE_TOKEN="fake-token", SUPPORT_REPO="org/repo"):
            with self.assertRaises(GitHubIssueError):
                _create_github_issue("title", "body", ["query"])

    @patch("support.views.urllib.request.urlopen")
    def test_succeeds_on_2xx_response(self, mock_urlopen) -> None:
        from support.views import _create_github_issue

        mock_response = MagicMock()
        mock_response.status = 201
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with self.settings(SUPPORT_ISSUE_TOKEN="fake-token", SUPPORT_REPO="org/repo"):
            _create_github_issue("title", "body", ["query"])

        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://api.github.com/repos/org/repo/issues")
        self.assertEqual(request.get_header("Authorization"), "Bearer fake-token")
