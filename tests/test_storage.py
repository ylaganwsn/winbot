import boto3
import pytest
from moto import mock_aws

from winbot import config, storage

BUCKET = "test-winbot-files"


@pytest.fixture
def bucket(monkeypatch):
    monkeypatch.setenv("WINBOT_FILES_BUCKET", BUCKET)
    with mock_aws():
        boto3.client("s3", region_name=config.REGION).create_bucket(Bucket=BUCKET)
        yield BUCKET


def keys_in(bucket_name):
    client = boto3.client("s3", region_name=config.REGION)
    response = client.list_objects_v2(Bucket=bucket_name)
    return sorted(item["Key"] for item in response.get("Contents", []))


def test_key_layout():
    assert storage.original_key("abc", "report.docx") == "documents/abc/original/report.docx"
    assert storage.pdf_key("abc") == "documents/abc/document.pdf"


def test_upload_then_download_round_trip(bucket, tmp_path):
    source = tmp_path / "in.txt"
    source.write_text("hello winbot")
    storage.upload_file(source, "documents/abc/original/in.txt")

    target = tmp_path / "out.txt"
    storage.download_file("documents/abc/original/in.txt", target)
    assert target.read_text() == "hello winbot"


def test_presigned_url_points_at_the_object(bucket):
    url = storage.presigned_url("documents/abc/document.pdf", content_type="application/pdf")
    assert BUCKET in url
    assert "documents/abc/document.pdf" in url
    assert "response-content-type=application" in url


def test_delete_removes_only_that_documents_files(bucket, tmp_path):
    source = tmp_path / "f.txt"
    source.write_text("x")
    storage.upload_file(source, "documents/abc/original/f.txt")
    storage.upload_file(source, "documents/abc/document.pdf")
    storage.upload_file(source, "documents/other/document.pdf")

    deleted = storage.delete_document_files("abc")

    assert deleted == 2
    assert keys_in(bucket) == ["documents/other/document.pdf"]


def test_delete_with_nothing_to_delete_is_fine(bucket):
    assert storage.delete_document_files("missing") == 0


def test_missing_bucket_setting_gives_a_clear_error(monkeypatch):
    monkeypatch.delenv("WINBOT_FILES_BUCKET", raising=False)
    with pytest.raises(RuntimeError, match="WINBOT_FILES_BUCKET"):
        config.files_bucket()