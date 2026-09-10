import boto3
import pytest
from equicast_core.goals import (
    MAX_GOALS,
    GoalLimitExceededError,
    GoalMappingConflictError,
    GoalNotFoundError,
    GoalsClient,
)
from moto import mock_aws

BUCKET = "equicast-user-data-test"


def _create(client: GoalsClient, user_id: str, **overrides) -> dict:
    fields = {
        "name": "House deposit",
        "purpose": "buy_home",
        "target_amount": 20000,
        **overrides,
    }
    return client.create_goal(user_id, **fields)


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        yield client


def test_list_goals_returns_empty_list_when_object_missing(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)

    assert client.list_goals("auth0|new-user") == []


def test_create_goal_persists_and_returns_the_goal(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)

    goal = _create(client, "auth0|abc123", account_ids=["acc-1"])

    assert goal["name"] == "House deposit"
    assert goal["purpose"] == "buy_home"
    assert goal["target_amount"] == 20000
    assert goal["account_ids"] == ["acc-1"]
    assert goal["pie_ids"] == []
    assert goal["status"] == "active"
    assert goal["created_at"] == goal["updated_at"]
    assert client.list_goals("auth0|abc123") == [goal]


def test_get_goal_returns_the_matching_goal(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    goal = _create(client, "auth0|abc123")

    assert client.get_goal("auth0|abc123", goal["id"]) == goal


def test_get_goal_raises_for_unknown_id(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)

    with pytest.raises(GoalNotFoundError):
        client.get_goal("auth0|abc123", "does-not-exist")


def test_create_goal_raises_once_limit_reached(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    for i in range(MAX_GOALS):
        _create(client, "auth0|abc123", name=f"goal{i}")

    with pytest.raises(GoalLimitExceededError):
        _create(client, "auth0|abc123", name="one too many")


def test_create_goal_respects_custom_max_goals(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client, max_goals=2)
    _create(client, "auth0|abc123", name="goal0")
    _create(client, "auth0|abc123", name="goal1")

    with pytest.raises(GoalLimitExceededError):
        _create(client, "auth0|abc123", name="goal2")


def test_create_goal_does_not_affect_other_users(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|user-a", name="A's goal")

    assert client.list_goals("auth0|user-b") == []


def test_create_goal_raises_when_account_id_already_mapped(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|abc123", name="first", account_ids=["acc-1"])

    with pytest.raises(GoalMappingConflictError):
        _create(client, "auth0|abc123", name="second", account_ids=["acc-1"])


def test_create_goal_raises_when_pie_id_already_mapped(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|abc123", name="first", pie_ids=["pie-1"])

    with pytest.raises(GoalMappingConflictError):
        _create(client, "auth0|abc123", name="second", pie_ids=["pie-1"])


def test_create_goal_allows_same_account_id_for_different_users(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|user-a", account_ids=["acc-1"])

    goal = _create(client, "auth0|user-b", account_ids=["acc-1"])

    assert goal["account_ids"] == ["acc-1"]


def test_update_goal_patches_fields_and_bumps_updated_at(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    goal = _create(client, "auth0|abc123")

    updated = client.update_goal("auth0|abc123", goal["id"], name="Renamed goal")

    assert updated["name"] == "Renamed goal"
    assert updated["updated_at"] >= goal["updated_at"]
    assert client.list_goals("auth0|abc123") == [updated]


def test_update_goal_raises_for_unknown_id(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|abc123")

    with pytest.raises(GoalNotFoundError):
        client.update_goal("auth0|abc123", "does-not-exist", name="x")


def test_update_goal_allows_keeping_its_own_mapped_account(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    goal = _create(client, "auth0|abc123", account_ids=["acc-1"])

    updated = client.update_goal("auth0|abc123", goal["id"], account_ids=["acc-1"], name="Renamed")

    assert updated["account_ids"] == ["acc-1"]


def test_update_goal_raises_when_remapping_to_another_goals_account(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|abc123", name="first", account_ids=["acc-1"])
    second = _create(client, "auth0|abc123", name="second", account_ids=["acc-2"])

    with pytest.raises(GoalMappingConflictError):
        client.update_goal("auth0|abc123", second["id"], account_ids=["acc-1"])


def test_delete_goal_removes_it(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)
    goal = _create(client, "auth0|abc123")

    client.delete_goal("auth0|abc123", goal["id"])

    assert client.list_goals("auth0|abc123") == []


def test_delete_goal_raises_for_unknown_id(s3_client) -> None:
    client = GoalsClient(BUCKET, s3_client=s3_client)

    with pytest.raises(GoalNotFoundError):
        client.delete_goal("auth0|abc123", "does-not-exist")


def test_create_goal_retries_on_conditional_write_conflict(s3_client) -> None:
    """Simulates another process's write landing between this client's
    get_object and put_object calls: the first put_object loses the
    conditional-write race (PreconditionFailed), and create_goal should
    retry against the now-current state rather than raising or clobbering
    the concurrent write."""
    client = GoalsClient(BUCKET, s3_client=s3_client)
    real_put_object = s3_client.put_object
    call_count = {"n": 0}

    def put_object_loses_race_once(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            real_put_object(
                Bucket=BUCKET,
                Key="goals/auth0|abc123.json",
                Body=b'{"goals": [{"id": "concurrent", "name": "Concurrent", '
                b'"purpose": "other", "custom_purpose": "x", "target_amount": 1, '
                b'"target_date": null, "account_ids": [], "pie_ids": [], '
                b'"status": "active", "created_at": "t", "updated_at": "t"}]}',
                ContentType="application/json",
            )
            raise s3_client.exceptions.ClientError(
                {"Error": {"Code": "PreconditionFailed", "Message": "x"}}, "PutObject"
            )
        return real_put_object(**kwargs)

    s3_client.put_object = put_object_loses_race_once

    goal = _create(client, "auth0|abc123", name="Mine")

    ids = {g["id"] for g in client.list_goals("auth0|abc123")}
    assert ids == {"concurrent", goal["id"]}
