import pytest
from fastapi.testclient import TestClient

from winbot import api, config, db, documents
from winbot.api import app

client = TestClient(app)


def upload(name="report.pdf", content=b"data"):
    return client.post("/documents", files={"file": (name, content, "application/pdf")})


@pytest.fixture
def processed(monkeypatch):
    """Replace process_upload with a fake that records what it was given."""
    seen = []

    def fake(path):
        seen.append({"name": path.name, "content": path.read_bytes()})
        return {
            "doc_id": "d1",
            "filename": path.name,
            "status": "ready",
            "created_at": "2026-01-01T00:00:00",
            "pages": 2,
            "chunks": 5,
        }

    monkeypatch.setattr(api.documents, "process_upload", fake)
    return seen


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_path_is_404():
    assert client.get("/nope").status_code == 404


def test_upload_returns_the_document_record(processed):
    response = upload("report.pdf", b"hello")
    assert response.status_code == 201
    body = response.json()
    assert body["doc_id"] == "d1"
    assert body["status"] == "ready"
    assert body["pages"] == 2
    assert processed == [{"name": "report.pdf", "content": b"hello"}]


def test_unsupported_type_is_415_and_not_processed(processed):
    response = upload("malware.exe")
    assert response.status_code == 415
    assert "Unsupported file type" in response.json()["detail"]
    assert processed == []


def test_file_without_extension_is_415(processed):
    assert upload("README").status_code == 415


def test_too_large_file_is_413_and_not_processed(processed, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    response = upload("report.pdf", b"x" * 11)
    assert response.status_code == 413
    assert processed == []


def test_file_exactly_at_the_limit_is_accepted(processed, monkeypatch):
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    assert upload("report.pdf", b"x" * 10).status_code == 201


@pytest.mark.parametrize(
    "sent, expected",
    [
        ("../../etc/passwd.pdf", "passwd.pdf"),
        ("C:\\Users\\me\\report.pdf", "report.pdf"),
        ("my report (1).pdf", "my report _1_.pdf"),
        ("résumé.pdf", "résumé.pdf"),
    ],
)
def test_filenames_are_sanitized(processed, sent, expected):
    assert upload(sent).status_code == 201
    assert processed[0]["name"] == expected


def test_no_readable_text_is_422_with_the_reason(monkeypatch):
    def fake(path):
        raise documents.NoReadableText("No readable text found.")

    monkeypatch.setattr(api.documents, "process_upload", fake)
    response = upload("scan.pdf")
    assert response.status_code == 422
    assert "No readable text" in response.json()["detail"]


def test_unexpected_failure_is_a_plain_500_without_internal_details(monkeypatch):
    def fake(path):
        raise RuntimeError("secret internal detail: bucket xyz")

    monkeypatch.setattr(api.documents, "process_upload", fake)
    response = upload("report.pdf")
    assert response.status_code == 500
    assert "secret" not in response.text


def test_list_documents_newest_first(aws):
    db.create_document("old", "a.pdf")
    db.create_document("new", "b.pdf")
    response = client.get("/documents")
    assert response.status_code == 200
    assert [d["doc_id"] for d in response.json()] == ["new", "old"]


def test_get_one_document(aws):
    db.create_document("d1", "a.pdf")
    db.update_document("d1", status="ready", pages=3, chunks=7)
    response = client.get("/documents/d1")
    assert response.status_code == 200
    assert response.json()["pages"] == 3


def test_get_missing_document_is_404(aws):
    assert client.get("/documents/nope").status_code == 404