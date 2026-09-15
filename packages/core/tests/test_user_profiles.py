from decimal import Decimal

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


def test_get_or_create_profile_creates_with_defaults_on_first_login(
    dynamodb_resource,
) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|new-user")

    assert profile == {
        "user_id": "auth0|new-user",
        "default_currency": "GBP",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|new-user"})["Item"]
    assert stored == profile


def test_get_or_create_profile_returns_existing_profile_unchanged(dynamodb_resource) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "EUR",
            "transaction_type": "TRANSACTION",
            "fx_warmup_currencies": ["EUR"],
            "tax_residency": "UK",
            "income_tax_band": "HIGHER",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|existing")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "EUR",
        "transaction_type": "TRANSACTION",
        "fx_warmup_currencies": ["EUR"],
        "tax_residency": "UK",
        "income_tax_band": "HIGHER",
        "dividend_allowance_used_by_tax_year": {},
    }


def test_get_or_create_profile_backfills_transaction_type_onto_existing_profile_missing_it(
    dynamodb_resource,
) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "EUR",
            "fx_warmup_currencies": ["EUR"],
            "tax_residency": "UK",
            "income_tax_band": "HIGHER",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|existing")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "EUR",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["EUR"],
        "tax_residency": "UK",
        "income_tax_band": "HIGHER",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_get_or_create_profile_backfills_fx_warmup_currencies_onto_existing_profile_missing_it(
    dynamodb_resource,
) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "EUR",
            "transaction_type": "TRANSACTION",
            "tax_residency": "UK",
            "income_tax_band": "HIGHER",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|existing")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "EUR",
        "transaction_type": "TRANSACTION",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "HIGHER",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_get_or_create_profile_backfills_tax_residency_onto_existing_profile_missing_it(
    dynamodb_resource,
) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "EUR",
            "transaction_type": "TRANSACTION",
            "fx_warmup_currencies": ["EUR"],
            "income_tax_band": "HIGHER",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|existing")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "EUR",
        "transaction_type": "TRANSACTION",
        "fx_warmup_currencies": ["EUR"],
        "tax_residency": "UK",
        "income_tax_band": "HIGHER",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_get_or_create_profile_backfills_income_tax_band_onto_existing_profile_missing_it(
    dynamodb_resource,
) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "EUR",
            "transaction_type": "TRANSACTION",
            "fx_warmup_currencies": ["EUR"],
            "tax_residency": "UK",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|existing")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "EUR",
        "transaction_type": "TRANSACTION",
        "fx_warmup_currencies": ["EUR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_get_or_create_profile_backfills_dividend_allowance_used_onto_existing_profile_missing_it(
    dynamodb_resource,
) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "EUR",
            "transaction_type": "TRANSACTION",
            "fx_warmup_currencies": ["EUR"],
            "tax_residency": "UK",
            "income_tax_band": "HIGHER",
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|existing")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "EUR",
        "transaction_type": "TRANSACTION",
        "fx_warmup_currencies": ["EUR"],
        "tax_residency": "UK",
        "income_tax_band": "HIGHER",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_get_or_create_profile_backfills_all_fields_when_none_are_present(
    dynamodb_resource,
) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={"user_id": "auth0|existing", "default_currency": "EUR"}
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.get_or_create_profile("auth0|existing")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "EUR",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }


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
        Item={
            "user_id": "auth0|existing",
            "default_currency": "GBP",
            "transaction_type": "AVERAGE",
            "fx_warmup_currencies": ["GBP", "USD", "EUR"],
            "tax_residency": "UK",
            "income_tax_band": "BASIC",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_default_currency("auth0|existing", "EUR")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "EUR",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_update_default_currency_creates_profile_first_if_missing(dynamodb_resource) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_default_currency("auth0|new-user", "INR")

    assert profile == {
        "user_id": "auth0|new-user",
        "default_currency": "INR",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }


def test_update_transaction_type_updates_existing_profile(dynamodb_resource) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "GBP",
            "transaction_type": "AVERAGE",
            "fx_warmup_currencies": ["GBP", "USD", "EUR"],
            "tax_residency": "UK",
            "income_tax_band": "BASIC",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_transaction_type("auth0|existing", "TRANSACTION")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "GBP",
        "transaction_type": "TRANSACTION",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_update_transaction_type_creates_profile_first_if_missing(dynamodb_resource) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_transaction_type("auth0|new-user", "TRANSACTION")

    assert profile == {
        "user_id": "auth0|new-user",
        "default_currency": "GBP",
        "transaction_type": "TRANSACTION",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }


def test_update_fx_warmup_currencies_updates_existing_profile(dynamodb_resource) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "GBP",
            "transaction_type": "AVERAGE",
            "fx_warmup_currencies": ["GBP", "USD", "EUR"],
            "tax_residency": "UK",
            "income_tax_band": "BASIC",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_fx_warmup_currencies("auth0|existing", ["GBP", "INR"])

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "GBP",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["GBP", "INR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_update_fx_warmup_currencies_creates_profile_first_if_missing(dynamodb_resource) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_fx_warmup_currencies("auth0|new-user", ["INR"])

    assert profile == {
        "user_id": "auth0|new-user",
        "default_currency": "GBP",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["INR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }


def test_update_tax_residency_updates_existing_profile(dynamodb_resource) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "GBP",
            "transaction_type": "AVERAGE",
            "fx_warmup_currencies": ["GBP", "USD", "EUR"],
            "tax_residency": "UK",
            "income_tax_band": "BASIC",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_tax_residency("auth0|existing", "UK")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "GBP",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_update_tax_residency_creates_profile_first_if_missing(dynamodb_resource) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_tax_residency("auth0|new-user", "UK")

    assert profile == {
        "user_id": "auth0|new-user",
        "default_currency": "GBP",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "BASIC",
        "dividend_allowance_used_by_tax_year": {},
    }


def test_update_income_tax_band_updates_existing_profile(dynamodb_resource) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "GBP",
            "transaction_type": "AVERAGE",
            "fx_warmup_currencies": ["GBP", "USD", "EUR"],
            "tax_residency": "UK",
            "income_tax_band": "BASIC",
            "dividend_allowance_used_by_tax_year": {},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_income_tax_band("auth0|existing", "HIGHER")

    assert profile == {
        "user_id": "auth0|existing",
        "default_currency": "GBP",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "HIGHER",
        "dividend_allowance_used_by_tax_year": {},
    }
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored == profile


def test_update_income_tax_band_creates_profile_first_if_missing(dynamodb_resource) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.update_income_tax_band("auth0|new-user", "ADDITIONAL")

    assert profile == {
        "user_id": "auth0|new-user",
        "default_currency": "GBP",
        "transaction_type": "AVERAGE",
        "fx_warmup_currencies": ["GBP", "USD", "EUR"],
        "tax_residency": "UK",
        "income_tax_band": "ADDITIONAL",
        "dividend_allowance_used_by_tax_year": {},
    }


def test_delete_profile_removes_the_item(dynamodb_resource) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)
    client.get_or_create_profile("auth0|abc123")

    client.delete_profile("auth0|abc123")

    assert "Item" not in dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|abc123"})


def test_delete_profile_is_a_no_op_when_none_exists(dynamodb_resource) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    client.delete_profile("auth0|abc123")  # doesn't raise


def test_add_dividend_allowance_used_creates_profile_first_if_missing(dynamodb_resource) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.add_dividend_allowance_used("auth0|new-user", "2026-27", 42.5)

    assert profile["dividend_allowance_used_by_tax_year"] == {"2026-27": Decimal("42.5")}


def test_add_dividend_allowance_used_starts_a_tax_year_at_zero(dynamodb_resource) -> None:
    dynamodb_resource.Table(TABLE).put_item(
        Item={
            "user_id": "auth0|existing",
            "default_currency": "GBP",
            "transaction_type": "AVERAGE",
            "fx_warmup_currencies": ["GBP", "USD", "EUR"],
            "tax_residency": "UK",
            "income_tax_band": "BASIC",
            "dividend_allowance_used_by_tax_year": {"2025-26": Decimal("500")},
        }
    )
    client = UserProfileClient(TABLE, resource=dynamodb_resource)

    profile = client.add_dividend_allowance_used("auth0|existing", "2026-27", 100)

    assert profile["dividend_allowance_used_by_tax_year"] == {
        "2025-26": Decimal("500"),
        "2026-27": Decimal("100"),
    }


def test_add_dividend_allowance_used_accumulates_within_the_same_tax_year(
    dynamodb_resource,
) -> None:
    client = UserProfileClient(TABLE, resource=dynamodb_resource)
    client.add_dividend_allowance_used("auth0|existing", "2026-27", 300)

    profile = client.add_dividend_allowance_used("auth0|existing", "2026-27", 250)

    assert profile["dividend_allowance_used_by_tax_year"] == {"2026-27": Decimal("550")}
    stored = dynamodb_resource.Table(TABLE).get_item(Key={"user_id": "auth0|existing"})["Item"]
    assert stored["dividend_allowance_used_by_tax_year"] == {"2026-27": Decimal("550")}
