from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from equicast_core import AccountNotFoundError

from transactions.import_views import _rebalance_pie_allocations_for_add, _validate_commit_rows

AUTH_HEADER = {"HTTP_AUTHORIZATION": "Bearer validtoken"}


def _authenticate(mock_jwks_client, mock_decode, user_id: str = "auth0|abc123") -> None:
    mock_jwks_client.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
    mock_decode.return_value = {"sub": user_id}


class RebalancePieAllocationsForAddTests(TestCase):
    def test_empty_existing_holdings_returns_no_reallocation(self) -> None:
        self.assertEqual(_rebalance_pie_allocations_for_add([], Decimal("100")), [])

    def test_scales_existing_holdings_down_and_sums_to_exactly_100(self) -> None:
        existing = [
            {"id": "h-1", "allocation_pct": 60},
            {"id": "h-2", "allocation_pct": 40},
        ]

        reallocate = _rebalance_pie_allocations_for_add(existing, Decimal("20"))

        total = sum(Decimal(str(r["allocation_pct"])) for r in reallocate) + Decimal("20")
        self.assertEqual(total, Decimal("100"))
        self.assertEqual(reallocate[0]["allocation_pct"], 48.0)  # 60 * (80/100)

    def test_rounding_remainder_is_absorbed_by_the_last_entry(self) -> None:
        """Three holdings whose allocations don't scale down to a clean
        2-decimal value each — the last entry must absorb whatever rounding
        remainder is left so the batch still sums to exactly 100, not an
        AllocationError-triggering near-100 total."""
        existing = [
            {"id": "h-1", "allocation_pct": 33.34},
            {"id": "h-2", "allocation_pct": 33.33},
            {"id": "h-3", "allocation_pct": 33.33},
        ]

        reallocate = _rebalance_pie_allocations_for_add(existing, Decimal("10"))

        total = sum(Decimal(str(r["allocation_pct"])) for r in reallocate) + Decimal("10")
        self.assertEqual(total, Decimal("100"))


class ValidateCommitRowsTests(TestCase):
    def test_valid_rows_return_none(self) -> None:
        rows = [{"type": "BUY", "date": "2024-01-01", "no_of_shares": 10, "price_native": 100}]
        self.assertIsNone(_validate_commit_rows(rows))

    def test_empty_rows_is_an_error(self) -> None:
        self.assertIsNotNone(_validate_commit_rows([]))

    def test_invalid_type_is_an_error(self) -> None:
        rows = [{"type": "DIVIDEND", "date": "2024-01-01", "no_of_shares": 10, "price_native": 100}]
        self.assertIsNotNone(_validate_commit_rows(rows))

    def test_missing_date_is_an_error(self) -> None:
        rows = [{"type": "BUY", "no_of_shares": 10, "price_native": 100}]
        self.assertIsNotNone(_validate_commit_rows(rows))

    def test_non_positive_shares_is_an_error(self) -> None:
        rows = [{"type": "BUY", "date": "2024-01-01", "no_of_shares": 0, "price_native": 100}]
        self.assertIsNotNone(_validate_commit_rows(rows))


class ImportPreviewViewTests(TestCase):
    def test_post_returns_401_when_unauthenticated(self) -> None:
        response = self.client.post(reverse("transactions-import-preview"))

        self.assertEqual(response.status_code, 401)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_unknown_preset(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("transactions-import-preview"), data={"preset": "bogus"}, **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_when_file_is_missing(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("transactions-import-preview"), data={"preset": "generic"}, **AUTH_HEADER
        )

        self.assertEqual(response.status_code, 400)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_a_malformed_csv(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        upload = SimpleUploadedFile("bad.csv", b"foo,bar\n1,2\n", content_type="text/csv")

        response = self.client.post(
            reverse("transactions-import-preview"),
            data={"preset": "generic", "file": upload},
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.json()["detail"])

    @patch("transactions.views._market_data_client")
    @patch("transactions.import_views._market_data_client")
    @patch("transactions.import_views._holdings_client")
    @patch("transactions.import_views._pies_client")
    @patch("transactions.import_views._accounts_client")
    @patch("transactions.import_views._client")
    @patch("transactions.import_views._profile_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_groups_for_resolved_and_unresolved_tickers(
        self,
        mock_jwks_client,
        mock_decode,
        mock_profile_client,
        mock_client,
        mock_accounts_client,
        mock_pies_client,
        mock_holdings_client,
        mock_market_data_client,
        mock_views_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "TRANSACTION",
            "default_currency": "GBP",
        }
        mock_accounts_client.list_accounts.return_value = []
        mock_pies_client.list_pies.return_value = []
        mock_holdings_client.list_holdings.return_value = []
        mock_market_data_client.get_profile.side_effect = lambda asset_class, ticker: (
            {"name": "Apple Inc.", "currency": "USD"}
            if ticker == "AAPL" and asset_class == "stock"
            else None
        )
        mock_views_market_data_client.get_profile.return_value = None
        mock_client.list_transactions.return_value = []

        csv_content = (
            b"date,ticker,asset_class,type,no_of_shares,price_native\n"
            b"2024-01-10,AAPL,stock,BUY,10,150.0\n"
            b"2024-01-11,ZZZZ,stock,BUY,5,10.0\n"
        )
        upload = SimpleUploadedFile("import.csv", csv_content, content_type="text/csv")

        response = self.client.post(
            reverse("transactions-import-preview"),
            data={"preset": "generic", "file": upload},
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        groups_by_ticker = {g["ticker"]: g for g in response.json()["groups"]}
        self.assertTrue(groups_by_ticker["AAPL"]["resolved"])
        self.assertEqual(groups_by_ticker["AAPL"]["name"], "Apple Inc.")
        self.assertEqual(groups_by_ticker["AAPL"]["mode_preview"]["no_of_shares"], 10.0)
        self.assertFalse(groups_by_ticker["ZZZZ"]["resolved"])
        self.assertIsNone(groups_by_ticker["ZZZZ"]["mode_preview"])

    @patch("transactions.views._market_data_client")
    @patch("transactions.import_views._market_data_client")
    @patch("transactions.import_views._holdings_client")
    @patch("transactions.import_views._pies_client")
    @patch("transactions.import_views._accounts_client")
    @patch("transactions.import_views._client")
    @patch("transactions.import_views._profile_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_reports_an_unparseable_row_without_aborting_the_rest_of_the_file(
        self,
        mock_jwks_client,
        mock_decode,
        mock_profile_client,
        mock_client,
        mock_accounts_client,
        mock_pies_client,
        mock_holdings_client,
        mock_market_data_client,
        mock_views_market_data_client,
    ) -> None:
        """Reproduces a real Trading 212 export: a `Market sell` for a
        fractional share cashed out after a corporate action reports
        `Price / share` as `0E-10`. That row must not take down the rest
        of an otherwise-large import — it's surfaced in `invalid_rows`
        instead, and the valid rows around it still parse."""
        _authenticate(mock_jwks_client, mock_decode)
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "TRANSACTION",
            "default_currency": "GBP",
        }
        mock_accounts_client.list_accounts.return_value = []
        mock_pies_client.list_pies.return_value = []
        mock_holdings_client.list_holdings.return_value = []
        mock_market_data_client.get_profile.return_value = {"name": "Carnival", "currency": "GBP"}
        mock_views_market_data_client.get_profile.return_value = None
        mock_client.list_transactions.return_value = []

        header = (
            "Action,Time (UTC),ISIN,Ticker,Name,ID,No. of shares,Price / share,"
            "Currency (Price / share),Exchange rate,Result,Currency (Result),Total,"
            "Currency (Total),Stamp duty reserve tax,Currency (Stamp duty reserve tax),"
            "Currency conversion fee,Currency (Currency conversion fee)\n"
        )
        rows = (
            "Market buy,2024-03-01 14:32:10,GB0031215220,CCL,Carnival,EOF001,10,148.0,"
            "GBP,,,,1480.00,GBP,,,,\n"
            "Market sell,2024-06-05 11:36:23,GB0031215220,CCL,Carnival,EOF002,0.1218194200,"
            "0E-10,GBX,,-2.51,GBP,0.00,GBP,,,,\n"
        )
        upload = SimpleUploadedFile(
            "trading212.csv", (header + rows).encode(), content_type="text/csv"
        )

        response = self.client.post(
            reverse("transactions-import-preview"),
            data={"preset": "trading212", "file": upload},
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["invalid_rows"]), 1)
        self.assertEqual(body["invalid_rows"][0]["row"], 3)
        self.assertEqual(body["invalid_rows"][0]["ticker"], "CCL")
        self.assertIn("Price / share", body["invalid_rows"][0]["reason"])
        # The valid BUY row survives even though a later row in the same
        # file was invalid.
        self.assertEqual(body["groups"][0]["rows"][0]["external_id"], "EOF001")

    @patch("transactions.views._market_data_client")
    @patch("transactions.import_views._market_data_client")
    @patch("transactions.import_views._holdings_client")
    @patch("transactions.import_views._pies_client")
    @patch("transactions.import_views._accounts_client")
    @patch("transactions.import_views._client")
    @patch("transactions.import_views._profile_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_preview_flags_average_mode_holdings_that_already_have_a_position(
        self,
        mock_jwks_client,
        mock_decode,
        mock_profile_client,
        mock_client,
        mock_accounts_client,
        mock_pies_client,
        mock_holdings_client,
        mock_market_data_client,
        mock_views_market_data_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "AVERAGE",
            "default_currency": "GBP",
        }
        mock_accounts_client.list_accounts.return_value = [{"id": "acc-1", "name": "ISA"}]
        mock_pies_client.list_pies.return_value = []
        mock_holdings_client.list_holdings.return_value = [
            {
                "id": "h-1",
                "ticker": "AAPL",
                "asset_class": "stock",
                "account_id": "acc-1",
                "pie_id": None,
                "watchlist_id": None,
            }
        ]
        mock_market_data_client.get_profile.return_value = {"name": "Apple Inc.", "currency": "USD"}
        mock_views_market_data_client.get_profile.return_value = None
        mock_client.list_transactions.return_value = [
            {
                "id": "t-existing",
                "type": "BUY",
                "no_of_shares": 2,
                "average_price_native": 90.0,
                "average_price": None,
                "date": "2023-12-01",
                "external_id": None,
            }
        ]

        csv_content = (
            b"date,ticker,asset_class,type,no_of_shares,price_native\n"
            b"2024-01-10,AAPL,stock,BUY,3,100.0\n"
        )
        upload = SimpleUploadedFile("import.csv", csv_content, content_type="text/csv")

        response = self.client.post(
            reverse("transactions-import-preview"),
            data={"preset": "generic", "file": upload},
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        existing = response.json()["groups"][0]["existing_holdings"][0]
        self.assertTrue(existing["already_has_position"])
        self.assertEqual(existing["combined_preview"]["no_of_shares"], 5.0)
        self.assertAlmostEqual(existing["combined_preview"]["average_price_native"], 96.0)

    @patch("transactions.views._market_data_client")
    @patch("transactions.import_views._market_data_client")
    @patch("transactions.import_views._holdings_client")
    @patch("transactions.import_views._pies_client")
    @patch("transactions.import_views._accounts_client")
    @patch("transactions.import_views._client")
    @patch("transactions.import_views._profile_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_preview_resolves_pie_name_and_its_parent_account_for_a_pie_holding(
        self,
        mock_jwks_client,
        mock_decode,
        mock_profile_client,
        mock_client,
        mock_accounts_client,
        mock_pies_client,
        mock_holdings_client,
        mock_market_data_client,
        mock_views_market_data_client,
    ) -> None:
        """An existing_holdings entry for a pie-scoped holding must carry
        enough to build a real label (e.g. "ISA → FutureFund") —
        account_name alone is always null for a pie holding (see
        HoldingsClient: a holding belongs to exactly one of account_id/
        pie_id/watchlist_id), so the pie's own name and its parent
        account's name are resolved separately."""
        _authenticate(mock_jwks_client, mock_decode)
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "TRANSACTION",
            "default_currency": "GBP",
        }
        mock_accounts_client.list_accounts.return_value = [{"id": "acc-1", "name": "ISA"}]
        mock_pies_client.list_pies.return_value = [
            {"id": "pie-1", "account_id": "acc-1", "name": "FutureFund"}
        ]
        mock_holdings_client.list_holdings.return_value = [
            {
                "id": "h-1",
                "ticker": "AAPL",
                "asset_class": "stock",
                "account_id": None,
                "pie_id": "pie-1",
                "watchlist_id": None,
            }
        ]
        mock_market_data_client.get_profile.return_value = {"name": "Apple Inc.", "currency": "USD"}
        mock_views_market_data_client.get_profile.return_value = None
        mock_client.list_transactions.return_value = []

        csv_content = (
            b"date,ticker,asset_class,type,no_of_shares,price_native\n"
            b"2024-01-10,AAPL,stock,BUY,3,100.0\n"
        )
        upload = SimpleUploadedFile("import.csv", csv_content, content_type="text/csv")

        response = self.client.post(
            reverse("transactions-import-preview"),
            data={"preset": "generic", "file": upload},
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        existing = response.json()["groups"][0]["existing_holdings"][0]
        self.assertIsNone(existing["account_name"])
        self.assertEqual(existing["pie_name"], "FutureFund")
        self.assertEqual(existing["pie_account_name"], "ISA")


class ImportCommitViewTests(TestCase):
    def test_post_returns_401_when_unauthenticated(self) -> None:
        response = self.client.post(
            reverse("transactions-import-commit"),
            data={"selections": []},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_post_returns_400_for_missing_selections(self, mock_jwks_client, mock_decode) -> None:
        _authenticate(mock_jwks_client, mock_decode)

        response = self.client.post(
            reverse("transactions-import-commit"),
            data={},
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 400)

    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    @patch("transactions.views._market_data_client")
    @patch("transactions.import_views._client")
    @patch("transactions.import_views._holdings_client")
    @patch("transactions.import_views._accounts_client")
    @patch("transactions.import_views._profile_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_average_mode_creates_new_position_for_a_new_account_holding(
        self,
        mock_jwks_client,
        mock_decode,
        mock_profile_client,
        mock_accounts_client,
        mock_holdings_client,
        mock_client,
        mock_views_market_data_client,
        mock_views_client,
        mock_views_holdings_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "AVERAGE",
            "default_currency": "GBP",
        }
        mock_accounts_client.get_account.return_value = {"id": "acc-1"}
        new_holding = {
            "id": "h-1",
            "ticker": "VOD",
            "asset_class": "stock",
            "account_id": "acc-1",
            "pie_id": None,
            "watchlist_id": None,
        }
        mock_holdings_client.create_holding.return_value = new_holding
        mock_client.list_transactions.return_value = []
        mock_client.create_transaction.return_value = {"id": "t-1"}
        mock_views_market_data_client.get_profile.return_value = None
        mock_views_client.list_transactions.return_value = []
        mock_views_holdings_client.update_holding_financials.return_value = new_holding

        response = self.client.post(
            reverse("transactions-import-commit"),
            data={
                "selections": [
                    {
                        "ticker": "VOD",
                        "asset_class": "stock",
                        "target": {"type": "account", "id": "acc-1"},
                        "rows": [
                            {
                                "external_id": "t212-1",
                                "date": "2024-01-10",
                                "type": "BUY",
                                "no_of_shares": 10,
                                "price_native": 100.0,
                                "fx_rate": None,
                            },
                            {
                                "external_id": "t212-2",
                                "date": "2024-02-10",
                                "type": "BUY",
                                "no_of_shares": 5,
                                "price_native": 110.0,
                                "fx_rate": None,
                            },
                        ],
                    }
                ]
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["holding_id"], "h-1")
        mock_client.create_transaction.assert_called_once()
        _, kwargs = mock_client.create_transaction.call_args
        self.assertEqual(kwargs["type"], "BUY")
        self.assertEqual(kwargs["no_of_shares"], 15.0)
        self.assertAlmostEqual(kwargs["average_price_native"], (10 * 100.0 + 5 * 110.0) / 15.0)
        self.assertEqual(kwargs["date"], "2024-01-10")

    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    @patch("transactions.views._market_data_client")
    @patch("transactions.import_views._client")
    @patch("transactions.import_views._holdings_client")
    @patch("transactions.import_views._profile_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_average_mode_extends_an_existing_position(
        self,
        mock_jwks_client,
        mock_decode,
        mock_profile_client,
        mock_holdings_client,
        mock_client,
        mock_views_market_data_client,
        mock_views_client,
        mock_views_holdings_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "AVERAGE",
            "default_currency": "GBP",
        }
        existing_holding = {
            "id": "h-1",
            "ticker": "VOD",
            "asset_class": "stock",
            "account_id": "acc-1",
            "pie_id": None,
            "watchlist_id": None,
        }
        mock_holdings_client.get_holding.return_value = existing_holding
        existing_buy = {
            "id": "t-existing",
            "type": "BUY",
            "no_of_shares": 2,
            "average_price_native": 90.0,
            "average_price": None,
            "date": "2023-12-01",
        }
        mock_client.list_transactions.return_value = [existing_buy]
        mock_client.update_transaction.return_value = {**existing_buy, "no_of_shares": 5}
        mock_views_market_data_client.get_profile.return_value = None
        mock_views_client.list_transactions.return_value = []
        mock_views_holdings_client.update_holding_financials.return_value = existing_holding

        response = self.client.post(
            reverse("transactions-import-commit"),
            data={
                "selections": [
                    {
                        "ticker": "VOD",
                        "asset_class": "stock",
                        "target": {"type": "existing_holding", "id": "h-1"},
                        "rows": [
                            {
                                "external_id": "t212-3",
                                "date": "2024-01-10",
                                "type": "BUY",
                                "no_of_shares": 3,
                                "price_native": 100.0,
                                "fx_rate": None,
                            }
                        ],
                    }
                ]
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["status"], "created")
        mock_client.update_transaction.assert_called_once()
        args, kwargs = mock_client.update_transaction.call_args
        self.assertEqual(args[2], "t-existing")
        self.assertEqual(kwargs["no_of_shares"], 5.0)
        self.assertAlmostEqual(kwargs["average_price_native"], 96.0)
        self.assertEqual(kwargs["date"], "2023-12-01")
        self.assertIsNone(kwargs["fx_rate"])

    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    @patch("transactions.views._market_data_client")
    @patch("transactions.import_views._client")
    @patch("transactions.import_views._holdings_client")
    @patch("transactions.import_views._profile_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_transaction_mode_skips_rows_with_a_known_external_id(
        self,
        mock_jwks_client,
        mock_decode,
        mock_profile_client,
        mock_holdings_client,
        mock_client,
        mock_views_market_data_client,
        mock_views_client,
        mock_views_holdings_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "TRANSACTION",
            "default_currency": "GBP",
        }
        holding = {
            "id": "h-1",
            "ticker": "VOD",
            "asset_class": "stock",
            "account_id": "acc-1",
            "pie_id": None,
            "watchlist_id": None,
        }
        mock_holdings_client.get_holding.return_value = holding
        mock_client.list_transactions.return_value = [
            {"id": "t-old", "type": "BUY", "external_id": "dup-1", "date": "2024-01-01"}
        ]
        mock_client.create_transaction.return_value = {"id": "t-new"}
        mock_views_market_data_client.get_profile.return_value = None
        mock_views_client.list_transactions.return_value = []
        mock_views_holdings_client.update_holding_financials.return_value = holding

        response = self.client.post(
            reverse("transactions-import-commit"),
            data={
                "selections": [
                    {
                        "ticker": "VOD",
                        "asset_class": "stock",
                        "target": {"type": "existing_holding", "id": "h-1"},
                        "rows": [
                            {
                                "external_id": "dup-1",
                                "date": "2024-01-01",
                                "type": "BUY",
                                "no_of_shares": 10,
                                "price_native": 100.0,
                                "fx_rate": None,
                            },
                            {
                                "external_id": "dup-2",
                                "date": "2024-02-01",
                                "type": "BUY",
                                "no_of_shares": 5,
                                "price_native": 105.0,
                                "fx_rate": None,
                            },
                        ],
                    }
                ]
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["results"][0]
        self.assertEqual(result["status"], "created")
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["skipped_duplicate_count"], 1)
        mock_client.create_transaction.assert_called_once()
        _, kwargs = mock_client.create_transaction.call_args
        self.assertEqual(kwargs["external_id"], "dup-2")

    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    @patch("transactions.views._market_data_client")
    @patch("transactions.import_views._client")
    @patch("transactions.import_views._holdings_client")
    @patch("transactions.import_views._accounts_client")
    @patch("transactions.import_views._profile_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_one_selection_failing_does_not_abort_the_batch(
        self,
        mock_jwks_client,
        mock_decode,
        mock_profile_client,
        mock_accounts_client,
        mock_holdings_client,
        mock_client,
        mock_views_market_data_client,
        mock_views_client,
        mock_views_holdings_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "AVERAGE",
            "default_currency": "GBP",
        }
        good_holding = {
            "id": "h-1",
            "ticker": "AAPL",
            "asset_class": "stock",
            "account_id": "acc-1",
            "pie_id": None,
            "watchlist_id": None,
        }

        def get_account(user_id, account_id):
            if account_id != "acc-1":
                raise AccountNotFoundError(account_id)

        mock_accounts_client.get_account.side_effect = get_account
        mock_holdings_client.create_holding.return_value = good_holding
        mock_client.list_transactions.return_value = []
        mock_client.create_transaction.return_value = {"id": "t-1"}
        mock_views_market_data_client.get_profile.return_value = None
        mock_views_client.list_transactions.return_value = []
        mock_views_holdings_client.update_holding_financials.return_value = good_holding

        response = self.client.post(
            reverse("transactions-import-commit"),
            data={
                "selections": [
                    {
                        "ticker": "AAPL",
                        "asset_class": "stock",
                        "target": {"type": "account", "id": "acc-1"},
                        "rows": [
                            {
                                "external_id": "ok-1",
                                "date": "2024-01-10",
                                "type": "BUY",
                                "no_of_shares": 10,
                                "price_native": 100.0,
                                "fx_rate": None,
                            }
                        ],
                    },
                    {
                        "ticker": "ZZZZ",
                        "asset_class": "stock",
                        "target": {"type": "account", "id": "acc-missing"},
                        "rows": [
                            {
                                "external_id": "bad-1",
                                "date": "2024-01-10",
                                "type": "BUY",
                                "no_of_shares": 1,
                                "price_native": 10.0,
                                "fx_rate": None,
                            }
                        ],
                    },
                ]
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(results[0]["ticker"], "AAPL")
        self.assertEqual(results[0]["status"], "created")
        self.assertEqual(results[1]["ticker"], "ZZZZ")
        self.assertEqual(results[1]["status"], "error")

    @patch("transactions.views._holdings_client")
    @patch("transactions.views._client")
    @patch("transactions.views._market_data_client")
    @patch("transactions.import_views._client")
    @patch("transactions.import_views._holdings_client")
    @patch("transactions.import_views._pies_client")
    @patch("transactions.import_views._profile_client")
    @patch("identity.authentication.jwt.decode")
    @patch("identity.authentication._jwks_client")
    def test_pie_target_rebalances_existing_allocations(
        self,
        mock_jwks_client,
        mock_decode,
        mock_profile_client,
        mock_pies_client,
        mock_holdings_client,
        mock_client,
        mock_views_market_data_client,
        mock_views_client,
        mock_views_holdings_client,
    ) -> None:
        _authenticate(mock_jwks_client, mock_decode)
        mock_profile_client.get_or_create_profile.return_value = {
            "transaction_type": "AVERAGE",
            "default_currency": "GBP",
        }
        mock_pies_client.get_pie.return_value = {"id": "pie-1"}
        mock_holdings_client.list_holdings.return_value = [
            {"id": "h-existing", "ticker": "MSFT", "allocation_pct": 100, "pie_id": "pie-1"},
        ]
        new_holding = {
            "id": "h-new",
            "ticker": "AAPL",
            "asset_class": "stock",
            "account_id": None,
            "pie_id": "pie-1",
            "watchlist_id": None,
        }
        mock_holdings_client.sync_pie_holdings.return_value = [
            {"id": "h-existing", "ticker": "MSFT", "allocation_pct": 80, "pie_id": "pie-1"},
            new_holding,
        ]
        mock_client.list_transactions.return_value = []
        mock_client.create_transaction.return_value = {"id": "t-1"}
        mock_views_market_data_client.get_profile.return_value = None
        mock_views_client.list_transactions.return_value = []
        mock_views_holdings_client.update_holding_financials.return_value = new_holding

        response = self.client.post(
            reverse("transactions-import-commit"),
            data={
                "selections": [
                    {
                        "ticker": "AAPL",
                        "asset_class": "stock",
                        "target": {"type": "pie", "id": "pie-1", "allocation_pct": 20},
                        "rows": [
                            {
                                "external_id": "ok-1",
                                "date": "2024-01-10",
                                "type": "BUY",
                                "no_of_shares": 10,
                                "price_native": 100.0,
                                "fx_rate": None,
                            }
                        ],
                    }
                ]
            },
            content_type="application/json",
            **AUTH_HEADER,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["status"], "created")
        mock_holdings_client.sync_pie_holdings.assert_called_once()
        _, kwargs = mock_holdings_client.sync_pie_holdings.call_args
        self.assertEqual(
            kwargs["add"], [{"ticker": "AAPL", "asset_class": "stock", "allocation_pct": 20.0}]
        )
        self.assertEqual(kwargs["reallocate"], [{"id": "h-existing", "allocation_pct": 80.0}])
