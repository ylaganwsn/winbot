import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from winbot import config


def _table(name):
    return boto3.resource("dynamodb", region_name=config.REGION).Table(name)


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def new_doc_id():
    return uuid.uuid4().hex


def _clean(value):
    """DynamoDB returns numbers as Decimal; turn them back into int or float."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def create_document(doc_id, filename, status="processing"):
    item = {
        "doc_id": doc_id,
        "filename": filename,
        "status": status,
        "created_at": _now(),
    }
    _table(config.DOCUMENTS_TABLE).put_item(Item=item)
    return item


def update_document(doc_id, **fields):
    """Change fields on an existing document. Raises KeyError if it doesn't exist."""
    names = {f"#{key}": key for key in fields}
    values = {f":{key}": value for key, value in fields.items()}
    expression = "SET " + ", ".join(f"#{key} = :{key}" for key in fields)
    try:
        response = _table(config.DOCUMENTS_TABLE).update_item(
            Key={"doc_id": doc_id},
            UpdateExpression=expression,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ConditionExpression="attribute_exists(doc_id)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise KeyError(doc_id) from error
        raise
    return _clean(response["Attributes"])


def get_document(doc_id):
    response = _table(config.DOCUMENTS_TABLE).get_item(Key={"doc_id": doc_id})
    item = response.get("Item")
    return _clean(item) if item else None


def list_documents():
    table = _table(config.DOCUMENTS_TABLE)
    items = []
    kwargs = {}
    while True:
        response = table.scan(**kwargs)
        items.extend(response["Items"])
        if "LastEvaluatedKey" not in response:
            break
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    items = [_clean(item) for item in items]
    return sorted(items, key=lambda item: item["created_at"], reverse=True)


def delete_document(doc_id):
    _table(config.DOCUMENTS_TABLE).delete_item(Key={"doc_id": doc_id})


def add_message(doc_id, question, answer, pages, provider):
    # the random suffix keeps two messages in the same microsecond from colliding
    item = {
        "doc_id": doc_id,
        "created_at": f"{_now()}#{uuid.uuid4().hex[:6]}",
        "question": question,
        "answer": answer,
        "pages": list(pages),
        "provider": provider,
    }
    _table(config.MESSAGES_TABLE).put_item(Item=item)
    return item


def _message_pages(doc_id):
    table = _table(config.MESSAGES_TABLE)
    kwargs = {"KeyConditionExpression": Key("doc_id").eq(doc_id)}
    while True:
        response = table.query(**kwargs)
        yield response["Items"]
        if "LastEvaluatedKey" not in response:
            break
        kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]


def list_messages(doc_id):
    """All messages for a document, oldest first."""
    messages = []
    for items in _message_pages(doc_id):
        messages.extend(_clean(item) for item in items)
    return messages


def delete_messages(doc_id):
    table = _table(config.MESSAGES_TABLE)
    deleted = 0
    for items in _message_pages(doc_id):
        with table.batch_writer() as batch:
            for item in items:
                batch.delete_item(
                    Key={"doc_id": item["doc_id"], "created_at": item["created_at"]}
                )
                deleted += 1
    return deleted