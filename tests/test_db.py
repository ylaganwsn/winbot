import boto3
import pytest
from moto import mock_aws

from winbot import config, db


@pytest.fixture
def tables(monkeypatch):
    counter = iter(range(100000))
    monkeypatch.setattr(db, "_now", lambda: f"t{next(counter):06d}")
    with mock_aws():
        client = boto3.client("dynamodb", region_name=config.REGION)
        client.create_table(
            TableName=config.DOCUMENTS_TABLE,
            AttributeDefinitions=[{"AttributeName": "doc_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "doc_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        client.create_table(
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


def test_new_doc_ids_are_unique():
    assert db.new_doc_id() != db.new_doc_id()


def test_create_then_get_document(tables):
    db.create_document("d1", "report.docx")
    doc = db.get_document("d1")
    assert doc["filename"] == "report.docx"
    assert doc["status"] == "processing"


def test_get_missing_document_returns_none(tables):
    assert db.get_document("nope") is None


def test_update_document_changes_fields_and_returns_plain_numbers(tables):
    db.create_document("d1", "report.docx")
    updated = db.update_document("d1", status="ready", pages=4, chunks=9)
    assert updated["status"] == "ready"
    assert updated["pages"] == 4
    assert isinstance(updated["pages"], int)
    assert db.get_document("d1")["chunks"] == 9


def test_update_missing_document_raises_key_error(tables):
    with pytest.raises(KeyError):
        db.update_document("nope", status="ready")
    assert db.get_document("nope") is None


def test_list_documents_newest_first(tables):
    db.create_document("old", "a.pdf")
    db.create_document("new", "b.pdf")
    assert [d["doc_id"] for d in db.list_documents()] == ["new", "old"]


def test_delete_document(tables):
    db.create_document("d1", "a.pdf")
    db.delete_document("d1")
    assert db.get_document("d1") is None
    assert db.list_documents() == []


def test_messages_come_back_in_order_with_plain_numbers(tables):
    db.add_message("d1", "first?", "one", [1, 3], "gemini")
    db.add_message("d1", "second?", "two", [2], "groq")
    messages = db.list_messages("d1")
    assert [m["question"] for m in messages] == ["first?", "second?"]
    assert messages[0]["pages"] == [1, 3]
    assert all(isinstance(p, int) for p in messages[0]["pages"])
    assert messages[1]["provider"] == "groq"


def test_messages_are_kept_per_document(tables):
    db.add_message("d1", "q1", "a1", [1], "gemini")
    db.add_message("d2", "q2", "a2", [2], "gemini")
    assert [m["question"] for m in db.list_messages("d1")] == ["q1"]


def test_delete_messages_removes_only_that_documents(tables):
    db.add_message("d1", "q1", "a1", [1], "gemini")
    db.add_message("d1", "q2", "a2", [1], "gemini")
    db.add_message("d2", "q3", "a3", [1], "gemini")
    assert db.delete_messages("d1") == 2
    assert db.list_messages("d1") == []
    assert len(db.list_messages("d2")) == 1


def test_messages_saved_at_the_same_instant_do_not_overwrite(tables, monkeypatch):
    monkeypatch.setattr(db, "_now", lambda: "same-instant")
    db.add_message("d1", "q1", "a1", [1], "gemini")
    db.add_message("d1", "q2", "a2", [1], "gemini")
    assert len(db.list_messages("d1")) == 2