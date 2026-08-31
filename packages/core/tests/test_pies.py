import boto3
import pytest
from equicast_core.pies import MAX_PIES, PieLimitExceededError, PieNotFoundError, PiesClient
from moto import mock_aws

BUCKET = "equicast-user-data-test"
ACCOUNT_ID = "acc-1"


def _create(client: PiesClient, user_id: str, **overrides) -> dict:
    fields = {
        "account_id": ACCOUNT_ID,
        "name": "Core ETFs",
        "description": "",
        **overrides,
    }
    return client.create_pie(user_id, **fields)


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        yield client


def test_list_pies_returns_empty_list_when_object_missing(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)

    assert client.list_pies("auth0|new-user") == []


def test_create_pie_persists_and_returns_the_pie(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)

    pie = _create(client, "auth0|abc123", description="Broad market")

    assert pie["account_id"] == ACCOUNT_ID
    assert pie["name"] == "Core ETFs"
    assert pie["description"] == "Broad market"
    assert pie["created_at"] == pie["updated_at"]
    assert client.list_pies("auth0|abc123") == [pie]


def test_list_pies_filters_by_account_id(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    pie_a = _create(client, "auth0|abc123", account_id="acc-a")
    _create(client, "auth0|abc123", account_id="acc-b")

    assert client.list_pies("auth0|abc123", account_id="acc-a") == [pie_a]


def test_get_pie_returns_the_matching_pie(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    pie = _create(client, "auth0|abc123")

    assert client.get_pie("auth0|abc123", pie["id"]) == pie


def test_get_pie_raises_for_unknown_id(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)

    with pytest.raises(PieNotFoundError):
        client.get_pie("auth0|abc123", "does-not-exist")


def test_create_pie_raises_once_limit_reached_for_that_account(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    for i in range(MAX_PIES):
        _create(client, "auth0|abc123", name=f"pie{i}")

    with pytest.raises(PieLimitExceededError):
        _create(client, "auth0|abc123", name="one too many")


def test_create_pie_cap_is_per_account_not_per_user(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    for i in range(MAX_PIES):
        _create(client, "auth0|abc123", account_id="acc-a", name=f"pie{i}")

    # A different account for the same user still has headroom.
    pie = _create(client, "auth0|abc123", account_id="acc-b", name="first in acc-b")

    assert pie["account_id"] == "acc-b"


def test_create_pie_respects_custom_max_pies_per_account(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client, max_pies_per_account=2)
    _create(client, "auth0|abc123", name="pie0")
    _create(client, "auth0|abc123", name="pie1")

    with pytest.raises(PieLimitExceededError):
        _create(client, "auth0|abc123", name="pie2")


def test_create_pie_does_not_affect_other_users(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|user-a", name="A's pie")

    assert client.list_pies("auth0|user-b") == []


def test_update_pie_patches_fields_and_bumps_updated_at(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    pie = _create(client, "auth0|abc123")

    updated = client.update_pie("auth0|abc123", pie["id"], name="Renamed pie")

    assert updated["name"] == "Renamed pie"
    assert updated["account_id"] == ACCOUNT_ID
    assert updated["updated_at"] >= pie["updated_at"]
    assert client.list_pies("auth0|abc123") == [updated]


def test_update_pie_raises_for_unknown_id(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|abc123")

    with pytest.raises(PieNotFoundError):
        client.update_pie("auth0|abc123", "does-not-exist", name="x")


def test_delete_pie_removes_it(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    pie = _create(client, "auth0|abc123")

    client.delete_pie("auth0|abc123", pie["id"])

    assert client.list_pies("auth0|abc123") == []


def test_delete_pie_raises_for_unknown_id(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)

    with pytest.raises(PieNotFoundError):
        client.delete_pie("auth0|abc123", "does-not-exist")


def test_delete_pies_for_account_removes_only_the_matching_ones(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    pie_a1 = _create(client, "auth0|abc123", account_id="acc-a")
    pie_a2 = _create(client, "auth0|abc123", account_id="acc-a")
    pie_b = _create(client, "auth0|abc123", account_id="acc-b")

    removed = client.delete_pies_for_account("auth0|abc123", "acc-a")

    assert removed == 2
    assert client.list_pies("auth0|abc123") == [pie_b]
    assert {p["id"] for p in [pie_a1, pie_a2]}.isdisjoint(
        {p["id"] for p in client.list_pies("auth0|abc123")}
    )


def test_delete_pies_for_account_is_a_noop_when_none_match(s3_client) -> None:
    client = PiesClient(BUCKET, s3_client=s3_client)
    pie = _create(client, "auth0|abc123", account_id="acc-a")

    removed = client.delete_pies_for_account("auth0|abc123", "acc-does-not-exist")

    assert removed == 0
    assert client.list_pies("auth0|abc123") == [pie]


def test_create_pie_retries_on_conditional_write_conflict(s3_client) -> None:
    """Simulates another process's write landing between this client's
    get_object and put_object calls: the first put_object loses the
    conditional-write race (PreconditionFailed), and create_pie should
    retry against the now-current state rather than raising or clobbering
    the concurrent write."""
    client = PiesClient(BUCKET, s3_client=s3_client)
    real_put_object = s3_client.put_object
    call_count = {"n": 0}

    def put_object_loses_race_once(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            real_put_object(
                Bucket=BUCKET,
                Key="pies/auth0|abc123.json",
                Body=b'{"pies": [{"id": "concurrent", "account_id": "acc-1", '
                b'"name": "Concurrent", "description": "", '
                b'"created_at": "t", "updated_at": "t"}]}',
                ContentType="application/json",
            )
            raise s3_client.exceptions.ClientError(
                {"Error": {"Code": "PreconditionFailed", "Message": "x"}}, "PutObject"
            )
        return real_put_object(**kwargs)

    s3_client.put_object = put_object_loses_race_once

    pie = _create(client, "auth0|abc123", name="Mine")

    ids = {p["id"] for p in client.list_pies("auth0|abc123")}
    assert ids == {"concurrent", pie["id"]}
