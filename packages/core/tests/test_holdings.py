import boto3
import pytest
from equicast_core.holdings import (
    MAX_HOLDINGS_FOR_ACCOUNT,
    MAX_HOLDINGS_FOR_PIE,
    MAX_HOLDINGS_FOR_WATCHLIST,
    AllocationError,
    HoldingAlreadyExistsError,
    HoldingLimitExceededError,
    HoldingNotFoundError,
    HoldingsClient,
)
from moto import mock_aws

BUCKET = "equicast-user-data-test"
ACCOUNT_ID = "acc-1"
PIE_ID = "pie-1"
WATCHLIST_ID = "watch-1"


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        yield client


def test_list_holdings_returns_empty_list_when_object_missing(s3_client) -> None:
    client = HoldingsClient(BUCKET, s3_client=s3_client)

    assert client.list_holdings("auth0|new-user") == []


class TestCreateHoldingAndListing:
    def test_create_holding_under_account_persists_and_returns_it(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        holding = client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
        )

        assert holding["ticker"] == "AAPL"
        assert holding["asset_class"] == "stock"
        assert holding["account_id"] == ACCOUNT_ID
        assert holding["pie_id"] is None
        assert holding["watchlist_id"] is None
        assert client.list_holdings("auth0|abc123") == [holding]

    def test_create_holding_under_watchlist_persists_and_returns_it(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        holding = client.create_holding(
            "auth0|abc123", ticker="EURUSD", asset_class="fx", watchlist_id=WATCHLIST_ID
        )

        assert holding["watchlist_id"] == WATCHLIST_ID
        assert holding["account_id"] is None
        assert holding["pie_id"] is None

    def test_create_holding_requires_exactly_one_parent(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(ValueError):
            client.create_holding("auth0|abc123", ticker="AAPL", asset_class="stock")

        with pytest.raises(ValueError):
            client.create_holding(
                "auth0|abc123",
                ticker="AAPL",
                asset_class="stock",
                account_id=ACCOUNT_ID,
                watchlist_id=WATCHLIST_ID,
            )

    def test_list_holdings_filters_by_each_parent(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        account_holding = client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
        )
        watchlist_holding = client.create_holding(
            "auth0|abc123", ticker="MSFT", asset_class="stock", watchlist_id=WATCHLIST_ID
        )
        pie_holding = client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
        )[0]

        assert client.list_holdings("auth0|abc123", account_id=ACCOUNT_ID) == [account_holding]
        assert client.list_holdings("auth0|abc123", watchlist_id=WATCHLIST_ID) == [
            watchlist_holding
        ]
        assert client.list_holdings("auth0|abc123", pie_id=PIE_ID) == [pie_holding]

    def test_get_holding_returns_the_matching_holding(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        holding = client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
        )

        assert client.get_holding("auth0|abc123", holding["id"]) == holding

    def test_get_holding_raises_for_unknown_id(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(HoldingNotFoundError):
            client.get_holding("auth0|abc123", "does-not-exist")

    def test_create_holding_raises_for_duplicate_ticker_in_same_parent(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
        )

        with pytest.raises(HoldingAlreadyExistsError):
            client.create_holding(
                "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
            )

    def test_create_holding_allows_same_ticker_across_different_parents(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
        )
        client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", watchlist_id=WATCHLIST_ID
        )
        client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id="acc-2"
        )

        assert len(client.list_holdings("auth0|abc123")) == 3

    def test_create_holding_raises_once_account_limit_reached(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client, max_holdings_for_account=2)
        client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
        )
        client.create_holding(
            "auth0|abc123", ticker="MSFT", asset_class="stock", account_id=ACCOUNT_ID
        )

        with pytest.raises(HoldingLimitExceededError):
            client.create_holding(
                "auth0|abc123", ticker="GOOG", asset_class="stock", account_id=ACCOUNT_ID
            )

    def test_create_holding_raises_once_watchlist_limit_reached(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client, max_holdings_for_watchlist=1)
        client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", watchlist_id=WATCHLIST_ID
        )

        with pytest.raises(HoldingLimitExceededError):
            client.create_holding(
                "auth0|abc123", ticker="MSFT", asset_class="stock", watchlist_id=WATCHLIST_ID
            )

    def test_default_caps_match_module_constants(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        assert client.max_holdings_for_account == MAX_HOLDINGS_FOR_ACCOUNT
        assert client.max_holdings_for_pie == MAX_HOLDINGS_FOR_PIE
        assert client.max_holdings_for_watchlist == MAX_HOLDINGS_FOR_WATCHLIST


class TestDeleteHolding:
    def test_delete_holding_removes_it(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        holding = client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
        )

        client.delete_holding("auth0|abc123", holding["id"])

        assert client.list_holdings("auth0|abc123") == []

    def test_delete_holding_raises_for_unknown_id(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(HoldingNotFoundError):
            client.delete_holding("auth0|abc123", "does-not-exist")

    def test_delete_holding_rejects_pie_scoped_holding(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        holding = client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
        )[0]

        with pytest.raises(ValueError):
            client.delete_holding("auth0|abc123", holding["id"])

    def test_delete_holdings_for_account_removes_only_the_matching_ones(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        h1 = client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id="acc-a"
        )
        h2 = client.create_holding(
            "auth0|abc123", ticker="MSFT", asset_class="stock", account_id="acc-a"
        )
        h3 = client.create_holding(
            "auth0|abc123", ticker="GOOG", asset_class="stock", account_id="acc-b"
        )

        removed = client.delete_holdings_for_account("auth0|abc123", "acc-a")

        assert removed == 2
        assert client.list_holdings("auth0|abc123") == [h3]
        assert {h1["id"], h2["id"]}.isdisjoint(
            {h["id"] for h in client.list_holdings("auth0|abc123")}
        )

    def test_delete_holdings_for_account_is_a_noop_when_none_match(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        holding = client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id="acc-a"
        )

        removed = client.delete_holdings_for_account("auth0|abc123", "acc-does-not-exist")

        assert removed == 0
        assert client.list_holdings("auth0|abc123") == [holding]

    def test_delete_holdings_for_watchlist_removes_only_the_matching_ones(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        h1 = client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", watchlist_id="watch-a"
        )
        h2 = client.create_holding(
            "auth0|abc123", ticker="MSFT", asset_class="stock", watchlist_id="watch-b"
        )

        removed = client.delete_holdings_for_watchlist("auth0|abc123", "watch-a")

        assert removed == 1
        assert client.list_holdings("auth0|abc123") == [h2]
        assert h1["id"] not in {h["id"] for h in client.list_holdings("auth0|abc123")}

    def test_delete_holdings_for_pies_removes_holdings_across_multiple_pies(
        self, s3_client
    ) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        client.sync_pie_holdings(
            "auth0|abc123",
            "pie-a",
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
        )
        client.sync_pie_holdings(
            "auth0|abc123",
            "pie-b",
            add=[{"ticker": "VXUS", "asset_class": "etf", "allocation_pct": 100}],
        )
        other = client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
        )

        removed = client.delete_holdings_for_pies("auth0|abc123", ["pie-a", "pie-b"])

        assert removed == 2
        assert client.list_holdings("auth0|abc123") == [other]

    def test_delete_holdings_for_pies_is_a_noop_when_none_match(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        assert client.delete_holdings_for_pies("auth0|abc123", ["pie-does-not-exist"]) == 0


class TestSyncPieHoldings:
    def test_add_holdings_summing_to_100_succeeds(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        result = client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[
                {"ticker": "VOO", "asset_class": "etf", "allocation_pct": 60},
                {"ticker": "VXUS", "asset_class": "etf", "allocation_pct": 40},
            ],
        )

        assert {(h["ticker"], h["allocation_pct"]) for h in result} == {("VOO", 60), ("VXUS", 40)}
        assert all(h["pie_id"] == PIE_ID for h in result)

    def test_add_holdings_not_summing_to_100_raises_and_writes_nothing(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(AllocationError):
            client.sync_pie_holdings(
                "auth0|abc123",
                PIE_ID,
                add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 60}],
            )

        assert client.list_holdings("auth0|abc123", pie_id=PIE_ID) == []

    def test_add_holding_with_non_positive_allocation_raises(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)

        with pytest.raises(AllocationError):
            client.sync_pie_holdings(
                "auth0|abc123",
                PIE_ID,
                add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 0}],
            )

    def test_add_duplicate_ticker_within_pie_raises(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
        )

        with pytest.raises(HoldingAlreadyExistsError):
            client.sync_pie_holdings(
                "auth0|abc123",
                PIE_ID,
                add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
                reallocate=[],
            )

    def test_add_second_holding_alongside_reallocating_the_first_to_stay_at_100(
        self, s3_client
    ) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        first = client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
        )[0]

        result = client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[{"ticker": "VXUS", "asset_class": "etf", "allocation_pct": 30}],
            reallocate=[{"id": first["id"], "allocation_pct": 70}],
        )

        assert {(h["ticker"], h["allocation_pct"]) for h in result} == {("VOO", 70), ("VXUS", 30)}

    def test_remove_holding_requires_remaining_to_still_sum_to_100(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        holdings = client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[
                {"ticker": "VOO", "asset_class": "etf", "allocation_pct": 60},
                {"ticker": "VXUS", "asset_class": "etf", "allocation_pct": 40},
            ],
        )
        voo_id = next(h["id"] for h in holdings if h["ticker"] == "VOO")
        vxus_id = next(h["id"] for h in holdings if h["ticker"] == "VXUS")

        with pytest.raises(AllocationError):
            client.sync_pie_holdings("auth0|abc123", PIE_ID, remove=[voo_id])

        result = client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            remove=[voo_id],
            reallocate=[{"id": vxus_id, "allocation_pct": 100}],
        )
        assert [h["ticker"] for h in result] == ["VXUS"]

    def test_removing_every_holding_leaves_an_empty_unconstrained_pie(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        holding = client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
        )[0]

        result = client.sync_pie_holdings("auth0|abc123", PIE_ID, remove=[holding["id"]])

        assert result == []
        assert client.list_holdings("auth0|abc123", pie_id=PIE_ID) == []

    def test_remove_unknown_id_raises(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
        )

        with pytest.raises(HoldingNotFoundError):
            client.sync_pie_holdings("auth0|abc123", PIE_ID, remove=["does-not-exist"])

    def test_reallocate_unknown_id_raises(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
        )

        with pytest.raises(HoldingNotFoundError):
            client.sync_pie_holdings(
                "auth0|abc123", PIE_ID, reallocate=[{"id": "does-not-exist", "allocation_pct": 50}]
            )

    def test_sync_pie_holdings_does_not_affect_other_pies_or_parents(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client)
        other_pie = client.sync_pie_holdings(
            "auth0|abc123",
            "pie-other",
            add=[{"ticker": "VOO", "asset_class": "etf", "allocation_pct": 100}],
        )[0]
        account_holding = client.create_holding(
            "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
        )

        client.sync_pie_holdings(
            "auth0|abc123",
            PIE_ID,
            add=[{"ticker": "VXUS", "asset_class": "etf", "allocation_pct": 100}],
        )

        assert client.list_holdings("auth0|abc123", pie_id="pie-other") == [other_pie]
        assert client.list_holdings("auth0|abc123", account_id=ACCOUNT_ID) == [account_holding]

    def test_sync_pie_holdings_raises_once_pie_limit_reached(self, s3_client) -> None:
        client = HoldingsClient(BUCKET, s3_client=s3_client, max_holdings_for_pie=1)

        with pytest.raises(HoldingLimitExceededError):
            client.sync_pie_holdings(
                "auth0|abc123",
                PIE_ID,
                add=[
                    {"ticker": "VOO", "asset_class": "etf", "allocation_pct": 60},
                    {"ticker": "VXUS", "asset_class": "etf", "allocation_pct": 40},
                ],
            )
        assert client.list_holdings("auth0|abc123", pie_id=PIE_ID) == []


def test_create_holding_retries_on_conditional_write_conflict(s3_client) -> None:
    """Simulates another process's write landing between this client's
    get_object and put_object calls: the first put_object loses the
    conditional-write race (PreconditionFailed), and create_holding should
    retry against the now-current state rather than raising or clobbering
    the concurrent write."""
    client = HoldingsClient(BUCKET, s3_client=s3_client)
    real_put_object = s3_client.put_object
    call_count = {"n": 0}

    def put_object_loses_race_once(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            real_put_object(
                Bucket=BUCKET,
                Key="holdings/auth0|abc123.json",
                Body=b'{"holdings": [{"id": "concurrent", "ticker": "MSFT", '
                b'"asset_class": "stock", "account_id": "acc-1", "pie_id": null, '
                b'"watchlist_id": null, "timestamp": "t"}]}',
                ContentType="application/json",
            )
            raise s3_client.exceptions.ClientError(
                {"Error": {"Code": "PreconditionFailed", "Message": "x"}}, "PutObject"
            )
        return real_put_object(**kwargs)

    s3_client.put_object = put_object_loses_race_once

    holding = client.create_holding(
        "auth0|abc123", ticker="AAPL", asset_class="stock", account_id=ACCOUNT_ID
    )

    ids = {h["id"] for h in client.list_holdings("auth0|abc123")}
    assert ids == {"concurrent", holding["id"]}
