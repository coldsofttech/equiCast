import boto3
import pytest
from equicast_core.transactions import (
    MAX_TRANSACTIONS_FOR_HOLDING,
    InsufficientSharesError,
    TransactionAlreadyExistsError,
    TransactionAmountError,
    TransactionLimitExceededError,
    TransactionNotFoundError,
    TransactionsClient,
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
            no_of_shares=10,
            average_price=152.5,
        )

        assert transaction["holding_id"] == HOLDING_ID
        assert transaction["no_of_shares"] == 10
        assert transaction["average_price"] == 152.5
        assert transaction["price"] is None
        assert transaction["date"] is None
        assert transaction["type"] is None
        assert transaction["created_at"] == transaction["updated_at"]
        assert client.list_transactions("auth0|abc123", holding_id=HOLDING_ID) == [transaction]
        assert client.list_transactions("auth0|abc123") == [transaction]

    def test_create_raises_for_non_positive_no_of_shares(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionAmountError):
            client.create_transaction(
                "auth0|abc123", HOLDING_ID, "AVERAGE", no_of_shares=0, average_price=100
            )

    def test_create_raises_for_non_positive_average_price(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionAmountError):
            client.create_transaction(
                "auth0|abc123", HOLDING_ID, "AVERAGE", no_of_shares=10, average_price=-1
            )

    def test_second_create_against_same_holding_raises(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123", HOLDING_ID, "AVERAGE", no_of_shares=10, average_price=100
        )

        with pytest.raises(TransactionAlreadyExistsError):
            client.create_transaction(
                "auth0|abc123", HOLDING_ID, "AVERAGE", no_of_shares=5, average_price=110
            )

    def test_create_allows_different_holdings(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123", "holding-a", "AVERAGE", no_of_shares=10, average_price=100
        )

        client.create_transaction(
            "auth0|abc123", "holding-b", "AVERAGE", no_of_shares=5, average_price=50
        )

        assert len(client.list_transactions("auth0|abc123")) == 2
        assert len(client.list_transactions("auth0|abc123", holding_id="holding-a")) == 1

    def test_create_does_not_affect_other_users(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|user-a", HOLDING_ID, "AVERAGE", no_of_shares=10, average_price=100
        )

        assert client.list_transactions("auth0|user-b") == []
        assert client.list_transactions("auth0|user-b", holding_id=HOLDING_ID) == []


class TestCreateTransactionModeTransaction:
    def test_create_buy_persists_and_returns_stable_shape(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price=152.5,
            date="2026-01-15",
            type="BUY",
        )

        assert transaction["no_of_shares"] == 10
        assert transaction["price"] == 152.5
        assert transaction["date"] == "2026-01-15"
        assert transaction["type"] == "BUY"
        assert transaction["average_price"] is None

    def test_create_raises_for_invalid_type(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionAmountError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "TRANSACTION",
                no_of_shares=10,
                price=100,
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
            price=100,
            date="2026-01-01",
            type="BUY",
        )

        sell = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=4,
            price=110,
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
            price=100,
            date="2026-01-01",
            type="BUY",
        )

        with pytest.raises(InsufficientSharesError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "TRANSACTION",
                no_of_shares=11,
                price=110,
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
                price=110,
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
            price=100,
            date="2026-01-01",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=5,
            price=110,
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
            price=90,
            date="2026-03-01",
            type="BUY",
        )
        sell = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=8,
            price=120,
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
            price=100,
            date="2026-01-01",
            type="BUY",
        )

        with pytest.raises(TransactionLimitExceededError):
            client.create_transaction(
                "auth0|abc123",
                HOLDING_ID,
                "TRANSACTION",
                no_of_shares=1,
                price=100,
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
                price=100,
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
            price=100,
            date="2025-06-01",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=5,
            price=110,
            date="2026-01-15",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=3,
            price=120,
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

    def test_average_mode_record_never_matches_a_date_filter(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123", "holding-avg", "AVERAGE", no_of_shares=10, average_price=100
        )

        assert client.list_transactions("auth0|abc123", year=2026) == []
        assert client.list_transactions("auth0|abc123", date_from="2000-01-01") == []


class TestGetTransaction:
    def test_get_returns_the_matching_transaction(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123", HOLDING_ID, "AVERAGE", no_of_shares=10, average_price=100
        )

        assert client.get_transaction("auth0|abc123", HOLDING_ID, transaction["id"]) == transaction

    def test_get_raises_for_unknown_id(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionNotFoundError):
            client.get_transaction("auth0|abc123", HOLDING_ID, "does-not-exist")

    def test_get_raises_when_transaction_belongs_to_a_different_holding(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123", "holding-a", "AVERAGE", no_of_shares=10, average_price=100
        )

        with pytest.raises(TransactionNotFoundError):
            client.get_transaction("auth0|abc123", "holding-b", transaction["id"])


class TestUpdateTransaction:
    def test_update_average_transaction_patches_fields_and_bumps_updated_at(
        self, s3_client
    ) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123", HOLDING_ID, "AVERAGE", no_of_shares=10, average_price=100
        )

        updated = client.update_transaction(
            "auth0|abc123", HOLDING_ID, transaction["id"], no_of_shares=15, average_price=105
        )

        assert updated["no_of_shares"] == 15
        assert updated["average_price"] == 105
        assert updated["updated_at"] >= transaction["updated_at"]

    def test_update_raises_for_non_positive_amount(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123", HOLDING_ID, "AVERAGE", no_of_shares=10, average_price=100
        )

        with pytest.raises(TransactionAmountError):
            client.update_transaction("auth0|abc123", HOLDING_ID, transaction["id"], no_of_shares=0)

    def test_update_raises_for_unknown_id(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionNotFoundError):
            client.update_transaction("auth0|abc123", HOLDING_ID, "does-not-exist", no_of_shares=1)

    def test_update_rejects_transaction_mode_record(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123",
            HOLDING_ID,
            "TRANSACTION",
            no_of_shares=10,
            price=100,
            date="2026-01-01",
            type="BUY",
        )

        with pytest.raises(ValueError):
            client.update_transaction("auth0|abc123", HOLDING_ID, transaction["id"], no_of_shares=5)


class TestDeleteTransaction:
    def test_delete_removes_it(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        transaction = client.create_transaction(
            "auth0|abc123", HOLDING_ID, "AVERAGE", no_of_shares=10, average_price=100
        )

        client.delete_transaction("auth0|abc123", HOLDING_ID, transaction["id"])

        assert client.list_transactions("auth0|abc123", holding_id=HOLDING_ID) == []

    def test_delete_raises_for_unknown_id(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(TransactionNotFoundError):
            client.delete_transaction("auth0|abc123", HOLDING_ID, "does-not-exist")


class TestHasTransactionsForHoldings:
    def test_returns_false_when_none_have_transactions(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)

        assert client.has_transactions_for_holdings("auth0|abc123", ["h-a", "h-b"]) is False

    def test_returns_true_when_one_has_a_transaction(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction("auth0|abc123", "h-b", "AVERAGE", no_of_shares=1, average_price=1)

        assert client.has_transactions_for_holdings("auth0|abc123", ["h-a", "h-b"]) is True


class TestDeleteTransactionsForHoldings:
    def test_deletes_only_the_matching_holdings_files(self, s3_client) -> None:
        client = TransactionsClient(BUCKET, s3_client=s3_client)
        client.create_transaction(
            "auth0|abc123", "holding-a", "AVERAGE", no_of_shares=10, average_price=100
        )
        client.create_transaction(
            "auth0|abc123", "holding-b", "AVERAGE", no_of_shares=5, average_price=50
        )
        client.create_transaction(
            "auth0|abc123", "holding-c", "AVERAGE", no_of_shares=1, average_price=1
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
            price=1,
            date="2026-01-01",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123",
            "holding-a",
            "TRANSACTION",
            no_of_shares=1,
            price=1,
            date="2026-01-02",
            type="BUY",
        )
        client.create_transaction(
            "auth0|abc123", "holding-b", "AVERAGE", no_of_shares=1, average_price=1
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
        price=100,
        date="2026-01-02",
        type="BUY",
    )

    ids = {t["id"] for t in client.list_transactions("auth0|abc123", holding_id=HOLDING_ID)}
    assert ids == {"concurrent", transaction["id"]}
