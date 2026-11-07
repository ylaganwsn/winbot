import boto3
import pytest
from moto import mock_aws

from winbot import config, documents

TEST_BUCKET = "test-winbot-files"


@pytest.fixture
def aws(monkeypatch):
    """A fake AWS with the files bucket and both DynamoDB tables."""
    monkeypatch.setenv("WINBOT_FILES_BUCKET", TEST_BUCKET)
    with mock_aws():
        boto3.client("s3", region_name=config.REGION).create_bucket(Bucket=TEST_BUCKET)
        dynamodb = boto3.client("dynamodb", region_name=config.REGION)
        dynamodb.create_table(
            TableName=config.DOCUMENTS_TABLE,
            AttributeDefinitions=[{"AttributeName": "doc_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "doc_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.create_table(
            TableName=config.MESSAGES_TABLE,
            AttributeDefinitions=[
                {"AttributeName": "doc_id", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
            ],
            KeySchema=[
                {"AttributeName": "doc_id", "KeyType": "HASH"},
                {"AttributeName": "created_at", "KeyType": "RANGE"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture(autouse=True)
def no_real_overview(monkeypatch):
    """No test may reach the real model. Tests that care replace this with their own fake."""
    monkeypatch.setattr(
        documents,
        "make_overview",
        lambda doc_id, pages: {"summary": "A test summary.", "faq": [], "suggestions": []},
    )