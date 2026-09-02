import boto3
import pytest
from equicast_core.user_profiles import UserProfileClient
from moto import mock_aws

TABLE = "equicast-user-profiles-test"


@pytest.fixture
def dynamodb_resource():
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="eu-west-1")
        resource.create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield resource


def test_get_or_create_profile_creates_with_default_currency_on_first_login(
    dynamodb_resource,
) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|new-user")

    assert profile == {"user_id": "auth0|new-user", "default_currency": "GBP"}
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|new-user"})["Item"]
    assert stored == profile


def test_get_or_create_profile_returns_existing_profile_unchanged(dynamodb_resource) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={"user_id": "auth0|existing", "default_currency": "EUR"}
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|existing")

    assert profile == {"user_id": "auth0|existing", "default_currency": "EUR"}


def test_get_or_create_profile_returns_winner_on_concurrent_create_race(dynamodb_resource) -> None:
    """Simulates another process's first-login write landing between this
    client's get_item and put_item calls: put_item's conditional check fails,
    and get_or_create_profile should re-fetch and return the winning item
    rather than raising."""
    table = dynamodb_resource.Table(TABLE)
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    def put_item_loses_race(**kwargs):
        table.put_item(Item={"user_id": "auth0|race", "default_currency": "USD"})
        raise table.meta.client.exceptions.ConditionalCheckFailedException(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "x"}}, "PutItem"
        )

    client._table.put_item = put_item_loses_race

    profile = client.get_or_create_profile("auth0|race")

    assert profile == {"user_id": "auth0|race", "default_currency": "USD"}


def test_update_default_currency_updates_existing_profile(dynamodb_resource) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={"user_id": "auth0|existing", "default_currency": "GBP"}
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_default_currency("auth0|existing", "EUR")

    assert profile == {"user_id": "auth0|existing", "default_currency": "EUR"}
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_update_default_currency_creates_profile_first_if_missing(dynamodb_resource) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_default_currency("auth0|new-user", "INR")

    assert profile == {"user_id": "auth0|new-user", "default_currency": "INR"}
