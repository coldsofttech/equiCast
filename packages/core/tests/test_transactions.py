from typing import Any

import boto3
import pytest
from equicast_core.transactions import (
    MAX_TRANSACTIONS_FOR_HOLDING,
    TRANSACTION_ACTIONS,
    InsufficientSharesError,
    TransactionAlreadyExistsError,
    TransactionAmountError,
    TransactionLimitExceededError,
    TransactionNotFoundError,
    TransactionsClient,
    compute_holding_rollup,
    compute_new_dividend_transactions,
    latest_paid_dividend_date,
)
from moto import mock_aws

BUCKET = "equicast-user-data-test"
HOLDING_ID = "holding-1"


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        yield client


def test_transaction_actions_includes_dividend() -> None:
    assert TRANSACTION_ACTIONS == {"BUY", "SELL", "DIVIDEND"}


def test_list_transactions_returns_empty_list_when_object_missing(s3_client) -> None:
    client = TransactionsClient(BUCKET, s3_client=s3_client)

    assert client.list_transactions("auth0|new-user") == []
    assert client.list_transactions("auth0|new-user", holding_id=HOLDING_ID) == []


class TestCreateAverageTransaction:
    def test_create_persists_and_returns_stable_shape(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=152.5,
            average_price=120.4,
            date="2026-01-15",
        )

        assert transaction["holding_id"] == HOLDING_ID
        assert transaction["no_of_shares"] == 10
        assert transaction["average_price_native"] == 152.5
        assert transaction["average_price"] == 120.4
        assert transaction["price_native"] is None
        assert transaction["price"] is None
        assert transaction["amount_native"] is None
        assert transaction["amount"] is None
        assert transaction["fx_rate"] is None
        assert transaction["date"] == "2026-01-15"
        assert transaction["type"] == "BUY"
        assert transaction["created_at"] == transaction["updated_at"]
        assert client.list_transactions("auth0|abc123", holding_id=HOLDING_ID) == [transaction]
        assert client.list_transactions("auth0|abc123") == [transaction]

    def test_create_stores_the_effective_fx_rate_whether_auto_resolved_or_overridden(
        self, s3_client
    ) -> None:
        """The core client itself doesn't distinguish "auto-resolved" from
        "user override" — that decision is the caller's (backend/
        transactions/views.py's resolve_converted_amounts); this just
        stores whatever `fx_rate` it's given, unconditionally."""
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            average_price=125,
            fx_rate=1.25,
            date="2026-01-15",
        )

        assert transaction["fx_rate"] == 1.25

    def test_create_raises_for_non_positive_no_of_shares(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionAmountError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "AVERAGE",
                type="BUY",
                no_of_shares=0,
                average_price_native=100,
                date="2026-01-15",
            )

    def test_create_raises_for_non_positive_average_price(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionAmountError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "AVERAGE",
                type="BUY",
                no_of_shares=10,
                average_price_native=-1,
                date="2026-01-15",
            )

    def test_create_raises_for_sell_type(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionAmountError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "AVERAGE",
                type="SELL",
                no_of_shares=1,
                average_price_native=1,
                date="2026-01-15",
            )

    def test_second_create_against_same_holding_raises(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        with pytest.raises(TransactionAlreadyExistsError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "AVERAGE",
                type="BUY",
                no_of_shares=5,
                average_price_native=110,
                date="2026-02-01",
            )

    def test_second_create_raises_even_against_a_legacy_type_none_record(self, s3_client) -> None:
        """A record predating the mandatory BUY/DIVIDEND shape still has
        type: None — TransactionAlreadyExistsError must still trip against
        it the same as a real BUY record."""
        s3_client.put_object(
            Bucket=BUCKET,
            Key=f"transactions/auth0|abc123/{HOLDING_ID}.json",
            Body=b'{"transactions": [{"id": "legacy", "holding_id": "holding-1", '
            b'"no_of_shares": 10, "average_price": 100, "price": null, "date": null, '
            b'"type": null, "created_at": "t", "updated_at": "t"}]}',
            ContentType="application/json",
        )
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionAlreadyExistsError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "AVERAGE",
                type="BUY",
                no_of_shares=5,
                average_price_native=110,
                date="2026-02-01",
            )

    def test_create_allows_different_holdings(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            "holding-a",
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        client.create_transaction(
            "auth0|abc123",
            "holding-b",
            "AVERAGE",
            type="BUY",
            no_of_shares=5,
            average_price_native=50,
            date="2026-01-15",
        )

        assert len(client.list_transactions("auth0|abc123")) == 2
        assert len(client.list_transactions("auth0|abc123", holding_id="holding-a")) == 1

    def test_create_does_not_affect_other_users(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|user-a",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        assert client.list_transactions("auth0|user-b") == []
        assert client.list_transactions("auth0|user-b", holding_id=HOLDING_ID) == []


class TestCreateDividendTransaction:
    def test_create_in_average_mode_persists_and_returns_stable_shape(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="DIVIDEND",
            amount_native=42.10,
            amount=33.68,
            date="2026-03-01",
        )

        assert transaction["type"] == "DIVIDEND"
        assert transaction["amount_native"] == 42.10
        assert transaction["amount"] == 33.68
        assert transaction["date"] == "2026-03-01"
        assert transaction["no_of_shares"] is None
        assert transaction["average_price_native"] is None
        assert transaction["average_price"] is None
        assert transaction["price_native"] is None
        assert transaction["price"] is None

    def test_create_in_transaction_mode_persists_and_returns_stable_shape(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            type="DIVIDEND",
            amount_native=15.75,
            date="2026-03-01",
        )

        assert transaction["type"] == "DIVIDEND"
        assert transaction["amount_native"] == 15.75
        assert transaction["amount"] is None
        assert transaction["no_of_shares"] is None
        assert transaction["price_native"] is None
        assert transaction["price"] is None

    def test_create_raises_for_non_positive_amount(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionAmountError):
            client.create_transaction(
                "auth0|abc123", HOLDING_ID, "AVERAGE", type="DIVIDEND",
                amount_native=0, date="2026-03-01"
            )

    def test_does_not_trip_already_exists_after_a_buy_in_average_mode(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        dividend = client.create_transaction(
            "auth0|abc123", HOLDING_ID, "AVERAGE", type="DIVIDEND",
            amount_native=42.10, date="2026-03-01"
        )

        assert dividend["type"] == "DIVIDEND"
        assert len(client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)) == 2

    def test_allows_any_number_of_dividends_per_holding(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        for i in range(3):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "AVERAGE",
                type="DIVIDEND",
                amount_native=10 + i,
                date=f"2026-0{i + 1}-01",
            )

        assert len(client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)) == 3

    def test_does_not_count_toward_a_sells_net_shares_check(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            type="BUY",
            no_of_shares=10,
            price_native=100,
            date="2026-01-01",
        )
        client.create_transaction(
            "auth0|abc123", HOLDING_ID, "TRANSACTION", type="DIVIDEND",
            amount_native=42.10, date="2026-02-01"
        )

        sell = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            type="SELL",
            no_of_shares=10,
            price_native=110,
            date="2026-03-01",
        )

        assert sell["type"] == "SELL"
        assert len(client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)) == 3


class TestCreateTransactionModeTransaction:
    def test_create_buy_persists_and_returns_stable_shape(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price_native=152.5,
            price=121.85,
            fx_rate=0.799,
            date="2026-01-15",
            type="BUY",
        )

        assert transaction["no_of_shares"] == 10
        assert transaction["price_native"] == 152.5
        assert transaction["price"] == 121.85
        assert transaction["fx_rate"] == 0.799
        assert transaction["date"] == "2026-01-15"
        assert transaction["type"] == "BUY"
        assert transaction["average_price_native"] is None
        assert transaction["average_price"] is None

    def test_converted_value_is_none_when_fx_rate_is_unresolved(self, s3_client) -> None:
        """The caller (backend/transactions/views.py's resolve_converted_
        amounts) passes `None` for the converted field when it couldn't
        resolve an FX rate — this client just stores that as given, the
        transaction is still recorded rather than rejected."""
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price_native=152.5,
            price=None,
            date="2026-01-15",
            type="BUY",
        )

        assert transaction["price_native"] == 152.5
        assert transaction["price"] is None

    def test_create_raises_for_invalid_type(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionAmountError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "TRANSACTION",
                no_of_shares=10,
                price_native=100,
                date="2026-01-15",
                type="HOLD",
            )

    def test_sell_within_net_shares_succeeds(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price_native=100,
            date="2026-01-01",
            type="BUY",
        )

        sell = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=4,
            price_native=110,
            date="2026-02-01",
            type="SELL",
        )

        assert sell["type"] == "SELL"
        assert len(client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)) == 2

    def test_sell_exceeding_net_shares_raises_and_writes_nothing(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price_native=100,
            date="2026-01-01",
            type="BUY",
        )

        with pytest.raises(InsufficientSharesError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "TRANSACTION",
                no_of_shares=11,
                price_native=110,
                date="2026-02-01",
                type="SELL",
            )

        assert len(client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)) == 1

    def test_sell_with_no_prior_buys_raises(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(InsufficientSharesError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "TRANSACTION",
                no_of_shares=1,
                price_native=110,
                date="2026-02-01",
                type="SELL",
            )

    def test_multiple_buys_and_sells_can_be_recorded(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price_native=100,
            date="2026-01-01",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=5,
            price_native=110,
            date="2026-02-01",
            type="SELL",
        )

        # Net is now 5 — a further BUY of 3 brings net to 8, so a SELL of 8
        # should succeed even though no single prior BUY covers it alone.
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=3,
            price_native=90,
            date="2026-03-01",
            type="BUY",
        )
        sell = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=8,
            price_native=120,
            date="2026-04-01",
            type="SELL",
        )

        assert sell["type"] == "SELL"
        assert len(client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)) == 4

    def test_create_raises_once_limit_reached(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client, max_transactions_for_holding=1)
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price_native=100,
            date="2026-01-01",
            type="BUY",
        )

        with pytest.raises(TransactionLimitExceededError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "TRANSACTION",
                no_of_shares=1,
                price_native=100,
                date="2026-01-02",
                type="BUY",
            )

    def test_negative_one_disables_the_cap(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client, max_transactions_for_holding=-1)
        for i in range(3):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "TRANSACTION",
                no_of_shares=1,
                price_native=100,
                date=f"2026-01-0{i + 1}",
                type="BUY",
            )

        assert len(client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)) == 3

    def test_default_cap_matches_module_constant(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        assert client.max_transactions_for_holding == MAX_TRANSACTIONS_FOR_HOLDING


class TestListTransactionsFilters:
    def _seed(self, client: TransactionsClient) -> None:
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price_native=100,
            date="2025-06-01",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=5,
            price_native=110,
            date="2026-01-15",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=3,
            price_native=120,
            date="2026-06-01",
            type="SELL",
        )

    def test_year_filters_to_matching_records(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        self._seed(client)

        result = client.list_transactions("auth0|abc123", holding_id=HOLDING_ID, year=2026)

        assert {t["date"] for t in result} == {"2026-01-15", "2026-06-01"}

    def test_year_accepts_string_or_int(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        self._seed(client)

        assert client.list_transactions(
            "auth0|abc123", holding_id=HOLDING_ID, year="2025"
        ) == client.list_transactions("auth0|abc123", holding_id=HOLDING_ID, year=2025)

    def test_date_range_filters_inclusively(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        self._seed(client)

        result = client.list_transactions(
            "auth0|abc123",
            holding_id=HOLDING_ID,
            date_from="2026-01-01",
            date_to="2026-01-31",
        )

        assert {t["date"] for t in result} == {"2026-01-15"}

    def test_date_filters_apply_without_holding_id_too(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        self._seed(client)

        result = client.list_transactions("auth0|abc123", year=2026)

        assert {t["date"] for t in result} == {"2026-01-15", "2026-06-01"}

    def test_average_mode_legacy_record_with_no_date_never_matches_a_date_filter(
        self, s3_client
    ) -> None:
        """A record predating the mandatory date field still has date:
        None — the current create_transaction path can't produce one
        (date is now a required kwarg), so this seeds one directly."""
        s3_client.put_object(
            Bucket=BUCKET,
            Key="transactions/auth0|abc123/holding-avg.json",
            Body=b'{"transactions": [{"id": "legacy", "holding_id": "holding-avg", '
            b'"no_of_shares": 10, "average_price": 100, "price": null, "date": null, '
            b'"type": null, "created_at": "t", "updated_at": "t"}]}',
            ContentType="application/json",
        )
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        assert client.list_transactions("auth0|abc123", year=2026) == []
        assert client.list_transactions("auth0|abc123", date_from="2000-01-01") == []


class TestLegacyRecordNormalization:
    def test_legacy_record_missing_amount_is_backfilled_to_none_on_read(self, s3_client) -> None:
        s3_client.put_object(
            Bucket=BUCKET,
            Key=f"transactions/auth0|abc123/{HOLDING_ID}.json",
            Body=b'{"transactions": [{"id": "legacy", "holding_id": "holding-1", '
            b'"no_of_shares": 10, "average_price": 100, "price": null, "date": null, '
            b'"type": null, "created_at": "t", "updated_at": "t"}]}',
            ContentType="application/json",
        )
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        transaction = client.get_transaction("auth0|abc123", HOLDING_ID, "legacy")

        assert transaction["amount"] is None
        listed = client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)
        assert listed[0]["amount"] is None
        assert client.list_transactions("auth0|abc123")[0]["amount"] is None

    def test_legacy_record_missing_native_counterparts_is_backfilled_to_none_on_read(
        self, s3_client
    ) -> None:
        """A record from before the native/converted split has no
        average_price_native/price_native/amount_native at all — its bare
        `average_price` stays exactly where it is (see module docstring:
        there's no way to know which currency it was actually in), only
        the new native counterpart backfills to None."""
        s3_client.put_object(
            Bucket=BUCKET,
            Key=f"transactions/auth0|abc123/{HOLDING_ID}.json",
            Body=b'{"transactions": [{"id": "legacy", "holding_id": "holding-1", '
            b'"no_of_shares": 10, "average_price": 100, "price": null, "date": null, '
            b'"type": null, "created_at": "t", "updated_at": "t"}]}',
            ContentType="application/json",
        )
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        transaction = client.get_transaction("auth0|abc123", HOLDING_ID, "legacy")

        assert transaction["average_price"] == 100
        assert transaction["average_price_native"] is None
        assert transaction["price_native"] is None
        assert transaction["amount_native"] is None
        assert transaction["fx_rate"] is None


class TestGetTransaction:
    def test_get_returns_the_matching_transaction(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        assert client.get_transaction("auth0|abc123", HOLDING_ID, transaction["id"]) == transaction

    def test_get_raises_for_unknown_id(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionNotFoundError):
            client.get_transaction("auth0|abc123", HOLDING_ID, "does-not-exist")

    def test_get_raises_when_transaction_belongs_to_a_different_holding(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            "holding-a",
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        with pytest.raises(TransactionNotFoundError):
            client.get_transaction("auth0|abc123", "holding-b", transaction["id"])


class TestUpdateTransaction:
    def test_update_average_transaction_patches_fields_and_bumps_updated_at(
        self, s3_client
    ) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        updated = client.update_transaction(
            "auth0|abc123",
            HOLDING_ID,
            transaction["id"],
            "AVERAGE",
            no_of_shares=15,
            average_price_native=105,
            average_price=84.3,
            date="2026-01-20",
        )

        assert updated["no_of_shares"] == 15
        assert updated["average_price_native"] == 105
        assert updated["average_price"] == 84.3
        assert updated["date"] == "2026-01-20"
        assert updated["updated_at"] >= transaction["updated_at"]

    def test_update_raises_for_non_positive_amount(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        with pytest.raises(TransactionAmountError):
            client.update_transaction(
                "auth0|abc123", HOLDING_ID, transaction["id"], "AVERAGE", no_of_shares=0
            )

    def test_update_raises_for_unknown_id(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionNotFoundError):
            client.update_transaction(
                "auth0|abc123", HOLDING_ID, "does-not-exist", "AVERAGE", no_of_shares=1
            )

    def test_update_rejects_transaction_mode_buy_sell_record(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price_native=100,
            date="2026-01-01",
            type="BUY",
        )

        with pytest.raises(ValueError):
            client.update_transaction(
                "auth0|abc123", HOLDING_ID, transaction["id"], "TRANSACTION", no_of_shares=5
            )

    def test_update_rejects_field_not_applicable_to_a_buy_record(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        with pytest.raises(ValueError):
            client.update_transaction(
                "auth0|abc123", HOLDING_ID, transaction["id"], "AVERAGE", amount_native=10
            )

    def test_update_rejects_converted_dividend_field_on_a_buy_record(self, s3_client) -> None:
        """`amount` (the DIVIDEND-only converted field) is rejected on a
        BUY record the same as `amount_native` is."""
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        with pytest.raises(ValueError):
            client.update_transaction(
                "auth0|abc123", HOLDING_ID, transaction["id"], "AVERAGE", amount=8
            )

    def test_update_rejects_field_not_applicable_to_a_dividend_record(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123", HOLDING_ID, "AVERAGE", type="DIVIDEND",
            amount_native=42.10, date="2026-03-01"
        )

        with pytest.raises(ValueError):
            client.update_transaction(
                "auth0|abc123", HOLDING_ID, transaction["id"], "AVERAGE", no_of_shares=5
            )

    def test_update_rejects_converted_buy_field_on_a_dividend_record(self, s3_client) -> None:
        """`average_price` (the BUY-only converted field) is rejected on a
        DIVIDEND record the same as `average_price_native` is."""
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123", HOLDING_ID, "AVERAGE", type="DIVIDEND",
            amount_native=42.10, date="2026-03-01"
        )

        with pytest.raises(ValueError):
            client.update_transaction(
                "auth0|abc123", HOLDING_ID, transaction["id"], "AVERAGE", average_price=90
            )

    def test_update_allows_a_dividend_record_in_transaction_mode(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            type="DIVIDEND",
            amount_native=15.75,
            date="2026-03-01",
        )

        updated = client.update_transaction(
            "auth0|abc123",
            HOLDING_ID,
            transaction["id"],
            "TRANSACTION",
            amount_native=20,
            amount=16,
            date="2026-03-02",
        )

        assert updated["amount_native"] == 20
        assert updated["amount"] == 16
        assert updated["date"] == "2026-03-02"

    def test_update_allows_fx_rate_on_an_average_buy_record(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            average_price=80,
            fx_rate=0.8,
            date="2026-01-15",
        )

        updated = client.update_transaction(
            "auth0|abc123",
            HOLDING_ID,
            transaction["id"],
            "AVERAGE",
            fx_rate=0.82,
            average_price=82,
        )

        assert updated["fx_rate"] == 0.82
        assert updated["average_price"] == 82

    def test_update_allows_fx_rate_on_a_dividend_record(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123", HOLDING_ID, "AVERAGE", type="DIVIDEND",
            amount_native=42.10, fx_rate=0.9, date="2026-03-01"
        )

        updated = client.update_transaction(
            "auth0|abc123", HOLDING_ID, transaction["id"], "AVERAGE", fx_rate=0.91
        )

        assert updated["fx_rate"] == 0.91

    def test_update_rejects_fx_rate_on_a_transaction_mode_buy_sell_record(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price_native=100,
            fx_rate=0.8,
            date="2026-01-01",
            type="BUY",
        )

        with pytest.raises(ValueError):
            client.update_transaction(
                "auth0|abc123", HOLDING_ID, transaction["id"], "TRANSACTION", fx_rate=0.85
            )


class TestDeleteTransaction:
    def test_delete_removes_it(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        client.delete_transaction("auth0|abc123", HOLDING_ID, transaction["id"])

        assert client.list_transactions("auth0|abc123", holding_id=HOLDING_ID) == []

    def test_delete_raises_for_unknown_id(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionNotFoundError):
            client.delete_transaction("auth0|abc123", HOLDING_ID, "does-not-exist")


class TestDividendsSyncedThroughWatermark:
    """The AVERAGE-mode auto-dividend feature's high-water mark (GitHub
    issue #123) — get_dividends_synced_through/advance_dividends_synced_through.
    The regression this exists to prevent: deleting an auto-created
    DIVIDEND transaction must not make sync_dividends_for_holdings
    (backend/transactions/views.py) recreate it on the very next GET."""

    def test_returns_none_when_never_set(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        assert client.get_dividends_synced_through("auth0|abc123", HOLDING_ID) is None

    def test_advance_sets_the_watermark_when_none_set_yet(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-03-01")

        assert client.get_dividends_synced_through("auth0|abc123", HOLDING_ID) == "2026-03-01"

    def test_advance_moves_the_watermark_forward(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-03-01")

        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-06-01")

        assert client.get_dividends_synced_through("auth0|abc123", HOLDING_ID) == "2026-06-01"

    def test_advance_never_moves_the_watermark_backward(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-06-01")

        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-01-01")

        assert client.get_dividends_synced_through("auth0|abc123", HOLDING_ID) == "2026-06-01"

    def test_create_transaction_preserves_an_existing_watermark(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-03-01")

        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )

        assert client.get_dividends_synced_through("auth0|abc123", HOLDING_ID) == "2026-03-01"

    def test_update_transaction_preserves_the_watermark_when_neither_date_nor_shares_change(
        self, s3_client
    ) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )
        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-03-01")

        client.update_transaction(
            "auth0|abc123", HOLDING_ID, transaction["id"], "AVERAGE", average_price_native=110
        )

        assert client.get_dividends_synced_through("auth0|abc123", HOLDING_ID) == "2026-03-01"

    def test_update_transaction_resets_the_watermark_when_no_of_shares_changes(
        self, s3_client
    ) -> None:
        """A share-count correction changes every already-synced DIVIDEND's
        amount (no_of_shares * per_share, computed at sync time) — rewinding
        the watermark to None lets the next sync_dividends_for_holdings
        rebuild the whole history against the corrected count."""
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )
        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-03-01")

        client.update_transaction(
            "auth0|abc123", HOLDING_ID, transaction["id"], "AVERAGE", no_of_shares=20
        )

        assert client.get_dividends_synced_through("auth0|abc123", HOLDING_ID) is None

    def test_update_transaction_resets_the_watermark_when_date_changes(self, s3_client) -> None:
        """Backdating the BUY can open up payouts between the new and old
        date that an already-advanced watermark had already skipped past —
        rewinding to None lets them be reconsidered."""
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )
        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-03-01")

        client.update_transaction(
            "auth0|abc123", HOLDING_ID, transaction["id"], "AVERAGE", date="2025-11-01"
        )

        assert client.get_dividends_synced_through("auth0|abc123", HOLDING_ID) is None

    def test_update_transaction_drops_auto_created_dividends_when_shares_change(
        self, s3_client
    ) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        buy = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="DIVIDEND",
            amount_native=42.10,
            date="2026-03-01",
        )
        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-03-01")

        client.update_transaction(
            "auth0|abc123", HOLDING_ID, buy["id"], "AVERAGE", no_of_shares=20
        )

        remaining = client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)
        assert [t["type"] for t in remaining] == ["BUY"]

    def test_delete_transaction_preserves_an_existing_watermark(self, s3_client) -> None:
        """The exact regression this feature exists to prevent: deleting an
        auto-created DIVIDEND transaction must not reset the watermark that
        keeps sync_dividends_for_holdings from recreating it."""
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "AVERAGE",
            type="DIVIDEND",
            amount_native=42.10,
            date="2026-03-01",
        )
        client.advance_dividends_synced_through("auth0|abc123", HOLDING_ID, "2026-03-01")

        client.delete_transaction("auth0|abc123", HOLDING_ID, transaction["id"])

        assert client.list_transactions("auth0|abc123", holding_id=HOLDING_ID) == []
        assert client.get_dividends_synced_through("auth0|abc123", HOLDING_ID) == "2026-03-01"


class TestHasTransactionsForHoldings:
    def test_returns_false_when_none_have_transactions(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        assert client.has_transactions_for_holdings("auth0|abc123", ["h-a", "h-b"]) is False

    def test_returns_true_when_one_has_a_transaction(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            "h-b",
            "AVERAGE",
            type="BUY",
            no_of_shares=1,
            average_price_native=1,
            date="2026-01-15",
        )

        assert client.has_transactions_for_holdings("auth0|abc123", ["h-a", "h-b"]) is True


class TestDeleteTransactionsForHoldings:
    def test_deletes_only_the_matching_holdings_files(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            "holding-a",
            "AVERAGE",
            type="BUY",
            no_of_shares=10,
            average_price_native=100,
            date="2026-01-15",
        )
        client.create_transaction(
            "auth0|abc123",
            "holding-b",
            "AVERAGE",
            type="BUY",
            no_of_shares=5,
            average_price_native=50,
            date="2026-01-15",
        )
        client.create_transaction(
            "auth0|abc123",
            "holding-c",
            "AVERAGE",
            type="BUY",
            no_of_shares=1,
            average_price_native=1,
            date="2026-01-15",
        )

        removed = client.delete_transactions_for_holdings("auth0|abc123", ["holding-b"])

        assert removed == 1
        assert client.list_transactions("auth0|abc123", holding_id="holding-b") == []
        assert len(client.list_transactions("auth0|abc123", holding_id="holding-a")) == 1
        assert len(client.list_transactions("auth0|abc123", holding_id="holding-c")) == 1

    def test_counts_every_record_across_multiple_holdings(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123",
            "holding-a",
            "TRANSACTION",
            no_of_shares=1,
            price_native=1,
            date="2026-01-01",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123",
            "holding-a",
            "TRANSACTION",
            no_of_shares=1,
            price_native=1,
            date="2026-01-02",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123",
            "holding-b",
            "AVERAGE",
            type="BUY",
            no_of_shares=1,
            average_price_native=1,
            date="2026-01-15",
        )

        removed = client.delete_transactions_for_holdings(
            "auth0|abc123", ["holding-a", "holding-b"]
        )

        assert removed == 3

    def test_is_a_noop_when_none_match(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        assert client.delete_transactions_for_holdings("auth0|abc123", ["nope"]) == 0


def test_create_transaction_retries_on_conditional_write_conflict(s3_client) -> None:
    """Simulates another process's write landing between this client's
    get_object and put_object calls: the first put_object loses the
    conditional-write race (PreconditionFailed), and create_transaction
    should retry against the now-current state rather than raising or
    clobbering the concurrent write."""
    client = TransactionsClient(BUCKET, s3_client=s3_client)
    real_put_object = s3_client.put_object
    call_count = {"n": 0}

    def put_object_loses_race_once(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            real_put_object(
                Bucket=BUCKET,
                Key=f"transactions/auth0|abc123/{HOLDING_ID}.json",
                Body=b'{"transactions": [{"id": "concurrent", "holding_id": "holding-1", '
                b'"no_of_shares": 1, "average_price": null, "price": 1, "date": "2026-01-01", '
                b'"type": "BUY", "created_at": "t", "updated_at": "t"}]}',
                ContentType="application/json",
            )
            raise s3_client.exceptions.ClientError(
                {"Error": {"Code": "PreconditionFailed", "Message": "x"}}, "PutObject"
            )
        return real_put_object(**kwargs)

    s3_client.put_object = put_object_loses_race_once

    transaction = client.create_transaction(
        "auth0|abc123",
        HOLDING_ID,
        "TRANSACTION",
        no_of_shares=10,
        price_native=100,
        date="2026-01-02",
        type="BUY",
    )

    ids = {t["id"] for t in client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)}
    assert ids == {"concurrent", transaction["id"]}


class TestComputeHoldingRollup:
    """See backend/transactions/views.py's _refresh_holding_rollup — this is
    the pure computation it (and holdings/views.py's nested-transaction
    create path) calls after every transaction create/update/delete to
    persist a holding's current position via HoldingsClient.update_holding_financials."""

    def test_average_mode_reads_the_single_buy_record(self) -> None:
        rollup = compute_holding_rollup(
            [
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "average_price_native": 150,
                    "average_price": 120,
                }
            ],
            "AVERAGE",
        )

        assert rollup == {
            "no_of_shares": 10.0,
            "average_price_native": 150.0,
            "average_price": 120.0,
            "invested_native": 1500.0,
            "invested": 1200.0,
            "dividends_native": 0.0,
            "dividends": 0.0,
        }

    def test_average_mode_returns_zeros_with_no_buy_record_yet(self) -> None:
        """The DIVIDEND record here has no `amount` (converted) key at all —
        same as a record written before the native/converted split, so its
        converted total is unresolvable (`dividends` is None) even though
        its native total is known."""
        rollup = compute_holding_rollup(
            [{"type": "DIVIDEND", "no_of_shares": None, "amount_native": 5}], "AVERAGE"
        )

        assert rollup == {
            "no_of_shares": 0,
            "average_price_native": None,
            "average_price": None,
            "invested_native": 0,
            "invested": 0,
            "dividends_native": 5.0,
            "dividends": None,
        }

    def test_average_mode_falls_back_to_the_legacy_bare_field_when_native_is_none(self) -> None:
        """A record from before the native/converted split has
        average_price_native backfilled to None (see
        equicast_core.transactions._normalize) — its bare average_price is
        treated as the native figure, but never as the converted one."""
        rollup = compute_holding_rollup(
            [
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "average_price_native": None,
                    "average_price": 150
                }
            ],
            "AVERAGE",
        )

        assert rollup["average_price_native"] == 150.0
        assert rollup["average_price"] is None
        assert rollup["invested_native"] == 1500.0
        assert rollup["invested"] is None

    def test_transaction_mode_computes_weighted_average_cost_across_multiple_buys(self) -> None:
        rollup = compute_holding_rollup(
            [
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "price_native": 100,
                    "price": 80,
                    "date": "2026-01-01",
                },
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "price_native": 200,
                    "price": 160,
                    "date": "2026-02-01",
                },
            ],
            "TRANSACTION",
        )

        assert rollup["no_of_shares"] == 20.0
        assert rollup["average_price_native"] == pytest.approx(150.0)
        assert rollup["average_price"] == pytest.approx(120.0)
        assert rollup["invested_native"] == pytest.approx(3000.0)
        assert rollup["invested"] == pytest.approx(2400.0)

    def test_transaction_mode_keeps_average_cost_unchanged_after_a_partial_sell(self) -> None:
        rollup = compute_holding_rollup(
            [
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "price_native": 100,
                    "price": 80,
                    "date": "2026-01-01",
                },
                {
                    "type": "SELL",
                    "no_of_shares": 4,
                    "price_native": 999,
                    "price": 999,
                    "date": "2026-03-01",
                },
            ],
            "TRANSACTION",
        )

        assert rollup["no_of_shares"] == 6.0
        assert rollup["average_price_native"] == pytest.approx(100.0)
        assert rollup["invested_native"] == pytest.approx(600.0)

    def test_transaction_mode_sorts_out_of_order_records_by_date(self) -> None:
        rollup = compute_holding_rollup(
            [
                {
                    "type": "SELL",
                    "no_of_shares": 4,
                    "price_native": 999,
                    "price": 999,
                    "date": "2026-03-01",
                },
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "price_native": 100,
                    "price": 80,
                    "date": "2026-01-01",
                },
            ],
            "TRANSACTION",
        )

        assert rollup["no_of_shares"] == 6.0
        assert rollup["average_price_native"] == pytest.approx(100.0)

    def test_transaction_mode_returns_none_avg_price_once_every_share_sold(self) -> None:
        rollup = compute_holding_rollup(
            [
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "price_native": 100,
                    "price": 80,
                    "date": "2026-01-01",
                },
                {
                    "type": "SELL",
                    "no_of_shares": 10,
                    "price_native": 200,
                    "price": 160,
                    "date": "2026-02-01",
                },
            ],
            "TRANSACTION",
        )

        assert rollup == {
            "no_of_shares": 0.0,
            "average_price_native": None,
            "average_price": None,
            "invested_native": 0,
            "invested": 0,
            "dividends_native": 0.0,
            "dividends": 0.0,
        }

    def test_transaction_mode_falls_back_to_the_legacy_bare_field_when_native_is_none(self) -> None:
        rollup = compute_holding_rollup(
            [
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "price_native": None,
                    "price": 100,
                    "date": "2026-01-01",
                }
            ],
            "TRANSACTION",
        )

        assert rollup["no_of_shares"] == 10.0
        assert rollup["average_price_native"] == pytest.approx(100.0)
        assert rollup["average_price"] is None
        assert rollup["invested"] is None

    def test_transaction_mode_ignores_dividend_records(self) -> None:
        rollup = compute_holding_rollup(
            [
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "price_native": 100,
                    "price": 80,
                    "date": "2026-01-01",
                },
                {
                    "type": "DIVIDEND",
                    "no_of_shares": None,
                    "amount_native": 5,
                    "date": "2026-02-01"
                },
            ],
            "TRANSACTION",
        )

        assert rollup["no_of_shares"] == 10.0
        assert rollup["dividends_native"] == pytest.approx(5.0)
        assert rollup["dividends"] is None

    def test_transaction_mode_sums_converted_dividends_when_resolved(self) -> None:
        rollup = compute_holding_rollup(
            [
                {
                    "type": "BUY",
                    "no_of_shares": 10,
                    "price_native": 100,
                    "price": 80,
                    "date": "2026-01-01",
                },
                {
                    "type": "DIVIDEND",
                    "no_of_shares": None,
                    "amount_native": 5,
                    "amount": 4,
                    "date": "2026-02-01",
                },
                {
                    "type": "DIVIDEND",
                    "no_of_shares": None,
                    "amount_native": 3,
                    "amount": 2.4,
                    "date": "2026-03-01",
                },
            ],
            "TRANSACTION",
        )

        assert rollup["dividends_native"] == pytest.approx(8.0)
        assert rollup["dividends"] == pytest.approx(6.4)

    def test_transaction_mode_dividends_unresolved_when_any_conversion_is_unknown(self) -> None:
        """One dividend's converted `amount` couldn't be resolved (e.g. no
        FX pair published that day) — the converted total is None rather
        than silently omitting that record's share, same "None when
        unresolvable" contract `invested` uses."""
        rollup = compute_holding_rollup(
            [
                {
                    "type": "DIVIDEND",
                    "no_of_shares": None,
                    "amount_native": 5,
                    "amount": 4,
                    "date": "2026-02-01",
                },
                {
                    "type": "DIVIDEND",
                    "no_of_shares": None,
                    "amount_native": 3,
                    "amount": None,
                    "date": "2026-03-01",
                },
            ],
            "TRANSACTION",
        )

        assert rollup["dividends_native"] == pytest.approx(8.0)
        assert rollup["dividends"] is None


class TestComputeNewDividendTransactions:
    """See backend/transactions/views.py's sync_dividends_for_holdings — the
    AVERAGE-mode auto-dividend feature (GitHub issue #123) that calls this
    to decide which paid payouts still need turning into a real DIVIDEND
    transaction."""

    BUY = {"type": "BUY", "no_of_shares": 10, "date": "2026-01-10"}

    def test_returns_nothing_with_no_buy_record_yet(self) -> None:
        dividends = [{"status": "paid", "ex_dividend_date": "2026-02-01", "price": 0.5}]
        assert compute_new_dividend_transactions([], dividends) == []

    def test_treats_a_legacy_type_none_record_as_the_buy(self) -> None:
        legacy_buy = {"type": None, "no_of_shares": 10, "date": "2026-01-10"}
        dividends = [{"status": "paid", "ex_dividend_date": "2026-02-01", "price": 0.5}]

        assert compute_new_dividend_transactions([legacy_buy], dividends) == [
            {"date": "2026-02-01", "amount_native": 5.0}
        ]

    def test_multiplies_per_share_price_by_the_buys_shares(self) -> None:
        dividends = [{"status": "paid", "ex_dividend_date": "2026-02-01", "price": 0.75}]

        assert compute_new_dividend_transactions([self.BUY], dividends) == [
            {"date": "2026-02-01", "amount_native": 7.5}
        ]

    def test_skips_a_payout_dated_before_the_buy(self) -> None:
        dividends = [{"status": "paid", "ex_dividend_date": "2026-01-01", "price": 0.5}]
        assert compute_new_dividend_transactions([self.BUY], dividends) == []

    def test_skips_a_payout_already_recorded_as_a_dividend_transaction(self) -> None:
        existing_dividend = {"type": "DIVIDEND", "date": "2026-02-01"}
        dividends = [{"status": "paid", "ex_dividend_date": "2026-02-01", "price": 0.5}]

        assert compute_new_dividend_transactions([self.BUY, existing_dividend], dividends) == []

    def test_skips_declared_and_estimated_payouts(self) -> None:
        dividends = [
            {"status": "declared", "ex_dividend_date": "2026-03-01", "price": 0.5},
            {"status": "estimated", "ex_dividend_date": "2026-04-01", "price": 0.5},
        ]
        assert compute_new_dividend_transactions([self.BUY], dividends) == []

    def test_skips_a_payout_missing_ex_date_or_price(self) -> None:
        dividends: list[dict[str, Any]] = [
            {"status": "paid", "ex_dividend_date": None, "price": 0.5},
            {"status": "paid", "ex_dividend_date": "2026-02-01", "price": None},
        ]
        assert compute_new_dividend_transactions([self.BUY], dividends) == []

    def test_returns_one_entry_per_qualifying_payout_in_given_order(self) -> None:
        dividends = [
            {"status": "paid", "ex_dividend_date": "2026-02-01", "price": 0.5},
            {"status": "paid", "ex_dividend_date": "2026-05-01", "price": 0.6},
        ]

        assert compute_new_dividend_transactions([self.BUY], dividends) == [
            {"date": "2026-02-01", "amount_native": 5.0},
            {"date": "2026-05-01", "amount_native": 6.0},
        ]

    def test_skips_a_payout_on_or_before_synced_through_even_if_not_recorded(self) -> None:
        """The deleted-dividend-comes-back regression: a payout already
        considered by an earlier sync (synced_through covers it) is never
        recreated, even though — because the user deleted the resulting
        transaction — nothing in existing_transactions matches its date
        any more."""
        dividends = [{"status": "paid", "ex_dividend_date": "2026-02-01", "price": 0.5}]

        assert (
            compute_new_dividend_transactions(
                [self.BUY], dividends, synced_through="2026-02-01"
            )
            == []
        )
        assert (
            compute_new_dividend_transactions(
                [self.BUY], dividends, synced_through="2026-03-01"
            )
            == []
        )

    def test_still_returns_a_payout_after_synced_through(self) -> None:
        dividends = [{"status": "paid", "ex_dividend_date": "2026-05-01", "price": 0.6}]

        assert compute_new_dividend_transactions(
            [self.BUY], dividends, synced_through="2026-02-01"
        ) == [{"date": "2026-05-01", "amount_native": 6.0}]


class TestLatestPaidDividendDate:
    """See backend/transactions/views.py's sync_dividends_for_holdings — the
    new dividends_synced_through watermark it advances a holding to after
    every sync (GitHub issue #123), via
    TransactionsClient.advance_dividends_synced_through."""

    def test_returns_none_with_no_paid_dividends_and_no_current_watermark(self) -> None:
        dividends = [{"status": "declared", "ex_dividend_date": "2026-03-01"}]
        assert latest_paid_dividend_date(dividends, None) is None

    def test_returns_the_latest_paid_ex_date(self) -> None:
        dividends = [
            {"status": "paid", "ex_dividend_date": "2026-02-01"},
            {"status": "paid", "ex_dividend_date": "2026-05-01"},
            {"status": "declared", "ex_dividend_date": "2026-08-01"},
        ]
        assert latest_paid_dividend_date(dividends, None) == "2026-05-01"

    def test_keeps_the_current_watermark_when_more_recent_than_any_paid_dividend(self) -> None:
        dividends = [{"status": "paid", "ex_dividend_date": "2026-02-01"}]
        assert latest_paid_dividend_date(dividends, "2026-06-01") == "2026-06-01"

    def test_ignores_a_paid_entry_missing_its_ex_date(self) -> None:
        dividends = [{"status": "paid", "ex_dividend_date": None}]
        assert latest_paid_dividend_date(dividends, "2026-01-01") == "2026-01-01"
