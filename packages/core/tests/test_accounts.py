import boto3
import pytest
from equicast_core.accounts import (
    MAX_ACCOUNTS,
    AccountAlreadyExistsError,
    AccountLimitExceededError,
    AccountNotFoundError,
    AccountsClient,
)
from moto import mock_aws

BUCKET = "equicast-user-data-test"


def _create(client: AccountsClient, user_id: str, **overrides) -> dict:
    fields = {
        "name": "ISA",
        "description": "",
        "account_type": "ISA",
        "currency": "GBP",
        "transaction_type": "TRANSACTION",
        **overrides,
    }
    return client.create_account(user_id, **fields)


@pytest.fixture
def s3_client():
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        yield client


def test_list_accounts_returns_empty_list_when_object_missing(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)

    assert client.list_accounts("auth0|new-user") == []


def test_create_account_persists_and_returns_the_account(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)

    account = _create(client, "auth0|abc123", description="Stocks & shares ISA")

    assert account["name"] == "ISA"
    assert account["description"] == "Stocks & shares ISA"
    assert account["account_type"] == "ISA"
    assert account["currency"] == "GBP"
    assert account["transaction_type"] == "TRANSACTION"
    assert account["created_at"] == account["updated_at"]
    assert client.list_accounts("auth0|abc123") == [account]


def test_get_account_returns_the_matching_account(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    account = _create(client, "auth0|abc123")

    assert client.get_account("auth0|abc123", account["id"]) == account


def test_get_account_raises_for_unknown_id(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)

    with pytest.raises(AccountNotFoundError):
        client.get_account("auth0|abc123", "does-not-exist")


def test_create_account_raises_once_limit_reached(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    for i in range(MAX_ACCOUNTS):
        _create(client, "auth0|abc123", name=f"acc{i}")

    with pytest.raises(AccountLimitExceededError):
        _create(client, "auth0|abc123", name="one too many")


def test_create_account_respects_custom_max_accounts(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client, max_accounts=2)
    _create(client, "auth0|abc123", name="acc0")
    _create(client, "auth0|abc123", name="acc1")

    with pytest.raises(AccountLimitExceededError):
        _create(client, "auth0|abc123", name="acc2")


def test_create_account_does_not_affect_other_users(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|user-a", name="A's ISA")

    assert client.list_accounts("auth0|user-b") == []


def test_create_account_raises_for_duplicate_name_case_insensitive(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|abc123", name="Stocks & Shares ISA")

    with pytest.raises(AccountAlreadyExistsError):
        _create(client, "auth0|abc123", name="Stocks & shares ISA")


def test_create_account_allows_duplicate_name_for_different_users(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|user-a", name="Stocks & Shares ISA")

    account = _create(client, "auth0|user-b", name="Stocks & Shares ISA")

    assert account["name"] == "Stocks & Shares ISA"


def test_update_account_patches_fields_and_bumps_updated_at(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    account = _create(client, "auth0|abc123")

    updated = client.update_account("auth0|abc123", account["id"], name="Renamed ISA")

    assert updated["name"] == "Renamed ISA"
    assert updated["account_type"] == "ISA"
    assert updated["updated_at"] >= account["updated_at"]
    assert client.list_accounts("auth0|abc123") == [updated]


def test_update_account_raises_for_unknown_id(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|abc123")

    with pytest.raises(AccountNotFoundError):
        client.update_account("auth0|abc123", "does-not-exist", name="x")


def test_update_account_raises_for_duplicate_name_case_insensitive(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    _create(client, "auth0|abc123", name="Stocks & Shares ISA")
    other = _create(client, "auth0|abc123", name="SIPP")

    with pytest.raises(AccountAlreadyExistsError):
        client.update_account("auth0|abc123", other["id"], name="stocks & shares isa")


def test_update_account_allows_keeping_its_own_name(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    account = _create(client, "auth0|abc123", name="Stocks & Shares ISA")

    updated = client.update_account(
        "auth0|abc123", account["id"], name="STOCKS & SHARES ISA", description="Updated"
    )

    assert updated["name"] == "STOCKS & SHARES ISA"


def test_delete_account_removes_it(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)
    account = _create(client, "auth0|abc123")

    client.delete_account("auth0|abc123", account["id"])

    assert client.list_accounts("auth0|abc123") == []


def test_delete_account_raises_for_unknown_id(s3_client) -> None:
    client = AccountsClient(BUCKET, s3_client=s3_client)

    with pytest.raises(AccountNotFoundError):
        client.delete_account("auth0|abc123", "does-not-exist")


def test_create_account_retries_on_conditional_write_conflict(s3_client) -> None:
    """Simulates another process's write landing between this client's
    get_object and put_object calls: the first put_object loses the
    conditional-write race (PreconditionFailed), and create_account should
    retry against the now-current state rather than raising or clobbering
    the concurrent write."""
    client = AccountsClient(BUCKET, s3_client=s3_client)
    real_put_object = s3_client.put_object
    call_count = {"n": 0}

    def put_object_loses_race_once(**kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            real_put_object(
                Bucket=BUCKET,
                Key="accounts/auth0|abc123.json",
                Body=b'{"accounts": [{"id": "concurrent", "name": "Concurrent", '
                b'"description": "", "account_type": "GIA", "currency": "GBP", '
                b'"created_at": "t", "updated_at": "t"}]}',
                ContentType="application/json",
            )
            raise s3_client.exceptions.ClientError(
                {"Error": {"Code": "PreconditionFailed", "Message": "x"}}, "PutObject"
            )
        return real_put_object(**kwargs)

    s3_client.put_object = put_object_loses_race_once

    account = _create(client, "auth0|abc123", name="Mine")

    ids = {a["id"] for a in client.list_accounts("auth0|abc123")}
    assert ids == {"concurrent", account["id"]}
