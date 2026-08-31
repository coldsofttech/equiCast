import boto3
import pytest
from equicast_core.watchlists import (
    MAX_WATCHLISTS,
    WatchlistLimitExceededError,
    WatchlistNotFoundError,
    WatchlistsClient,
)
from moto import mock_aws

BUCKET = "equicast-user-data-test"


def _create(client: WatchlistsClient, user_id: str, **overrides) -> dict:
    fields = {
        "name": "Tech Watch",
        "description": "",
        **overrides,
    }
    return client.create_watchlist(user_id, **fields)


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        yield client


def test_list_watchlists_returns_empty_list_when_object_missing(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)

    assert client.list_watchlists("auth0|new-user") == []


def test_create_watchlist_persists_and_returns_the_watchlist(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)

    watchlist = _create(client, "auth0|abc123", description="Big tech names")

    assert watchlist["name"] == "Tech Watch"
    assert watchlist["description"] == "Big tech names"
    assert watchlist["created_at"] == watchlist["updated_at"]
    assert client.list_watchlists("auth0|abc123") == [watchlist]


def test_get_watchlist_returns_the_matching_watchlist(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)
    watchlist = _create(client, "auth0|abc123")

    assert client.get_watchlist("auth0|abc123", watchlist["id"]) == watchlist


def test_get_watchlist_raises_for_unknown_id(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)

    with pytest.raises(WatchlistNotFoundError):
        client.get_watchlist("auth0|abc123", "does-not-exist")


def test_create_watchlist_raises_once_limit_reached(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)
    for i in range(MAX_WATCHLISTS):
        _create(client, "auth0|abc123", name=f"watch{i}")

    with pytest.raises(WatchlistLimitExceededError):
        _create(client, "auth0|abc123", name="one too many")


def test_create_watchlist_respects_custom_max_watchlists(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client, max_watchlists=2)
    _create(client, "auth0|abc123", name="watch0")
    _create(client, "auth0|abc123", name="watch1")

    with pytest.raises(WatchlistLimitExceededError):
        _create(client, "auth0|abc123", name="watch2")


def test_create_watchlist_does_not_affect_other_users(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|user-a", name="A's watchlist")

    assert client.list_watchlists("auth0|user-b") == []


def test_update_watchlist_patches_fields_and_bumps_updated_at(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)
    watchlist = _create(client, "auth0|abc123")

    updated = client.update_watchlist("auth0|abc123", watchlist["id"], name="Renamed watchlist")

    assert updated["name"] == "Renamed watchlist"
    assert updated["updated_at"] >= watchlist["updated_at"]
    assert client.list_watchlists("auth0|abc123") == [updated]


def test_update_watchlist_raises_for_unknown_id(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|abc123")

    with pytest.raises(WatchlistNotFoundError):
        client.update_watchlist("auth0|abc123", "does-not-exist", name="x")


def test_delete_watchlist_removes_it(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)
    watchlist = _create(client, "auth0|abc123")

    client.delete_watchlist("auth0|abc123", watchlist["id"])

    assert client.list_watchlists("auth0|abc123") == []


def test_delete_watchlist_raises_for_unknown_id(s3_client) -> None:
    client = WatchlistsClient(BUCKET, s3_client=s3_client)

    with pytest.raises(WatchlistNotFoundError):
        client.delete_watchlist("auth0|abc123", "does-not-exist")


def test_create_watchlist_retries_on_conditional_write_conflict(s3_client) -> None:
    """Simulates another process's write landing between this client's
    get_object and put_object calls: the first put_object loses the
    conditional-write race (PreconditionFailed), and create_watchlist should
    retry against the now-current state rather than raising or clobbering
    the concurrent write."""
    client = WatchlistsClient(BUCKET, s3_client=s3_client)
    real_put_object = s3_client.put_object
    call_count = {"n": 0}

    def put_object_loses_race_once(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            real_put_object(
                Bucket=BUCKET,
                Key="watchlists/auth0|abc123.json",
                Body=b'{"watchlists": [{"id": "concurrent", "name": "Concurrent", '
                b'"description": "", "created_at": "t", "updated_at": "t"}]}',
                ContentType="application/json",
            )
            raise s3_client.exceptions.ClientError(
                {"Error": {"Code": "PreconditionFailed", "Message": "x"}}, "PutObject"
            )
        return real_put_object(**kwargs)

    s3_client.put_object = put_object_loses_race_once

    watchlist = _create(client, "auth0|abc123", name="Mine")

    ids = {w["id"] for w in client.list_watchlists("auth0|abc123")}
    assert ids == {"concurrent", watchlist["id"]}
