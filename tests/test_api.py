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
    
@pytest.fixture
def ready_document(aws):
    db.create_document("d1", "report.pdf")
    db.update_document("d1", status="ready", pages=2, chunks=5)


@pytest.fixture
def answers(monkeypatch):
    """Replace the real question answering with a fake that records its calls."""
    calls = []

    def fake(question, doc_id=None):
        calls.append((question, doc_id))
        return {"answer": "Amazon RDS", "pages": [1, 3], "provider": "gemini"}

    monkeypatch.setattr(api, "answer_question", fake)
    return calls


def ask(doc_id="d1", question="Which service costs the most?"):
    return client.post(f"/documents/{doc_id}/ask", json={"question": question})


def test_ask_returns_the_answer_and_saves_it(ready_document, answers):
    response = ask()
    assert response.status_code == 200
    assert response.json() == {"answer": "Amazon RDS", "pages": [1, 3], "provider": "gemini"}
    assert answers == [("Which service costs the most?", "d1")]

    saved = db.list_messages("d1")
    assert len(saved) == 1
    assert saved[0]["question"] == "Which service costs the most?"
    assert saved[0]["pages"] == [1, 3]


def test_ask_trims_the_question(ready_document, answers):
    ask(question="  Which service costs the most?  ")
    assert answers[0][0] == "Which service costs the most?"


def test_ask_unknown_document_is_404(aws, answers):
    assert ask("nope").status_code == 404
    assert answers == []


@pytest.mark.parametrize("status", ["processing", "failed"])
def test_ask_document_that_is_not_ready_is_409(aws, answers, status):
    db.create_document("d1", "report.pdf")
    db.update_document("d1", status=status)
    assert ask().status_code == 409
    assert answers == []


@pytest.mark.parametrize("question", ["", "   ", "x" * 1001])
def test_bad_questions_are_422_and_never_answered(ready_document, answers, question):
    assert ask(question=question).status_code == 422
    assert answers == []


def test_answer_failure_is_a_plain_502_and_nothing_is_saved(ready_document, monkeypatch, caplog):
    def broken(question, doc_id=None):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(api, "answer_question", broken)
    with caplog.at_level("ERROR", logger="uvicorn.error"):
        response = ask()

    assert response.status_code == 502
    assert "secret" not in response.text
    assert "secret internal detail" in caplog.text
    assert db.list_messages("d1") == []


def test_history_save_failure_still_returns_the_answer(ready_document, answers, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError("table unavailable")

    monkeypatch.setattr(api.db, "add_message", broken)
    with caplog.at_level("ERROR", logger="uvicorn.error"):
        response = ask()

    assert response.status_code == 200
    assert response.json()["answer"] == "Amazon RDS"
    assert "table unavailable" in caplog.text


def test_messages_come_back_in_order(ready_document, answers):
    ask(question="first?")
    ask(question="second?")
    response = client.get("/documents/d1/messages")
    assert response.status_code == 200
    assert [m["question"] for m in response.json()] == ["first?", "second?"]
    assert response.json()[0]["provider"] == "gemini"


def test_messages_for_unknown_document_is_404(aws):
    assert client.get("/documents/nope/messages").status_code == 404
    
def test_message_timestamps_have_no_internal_suffix(ready_document, answers):
    ask()
    created_at = client.get("/documents/d1/messages").json()[0]["created_at"]
    assert "#" not in created_at
    assert created_at.startswith("20")
    
def test_file_link_points_at_the_pdf(ready_document):
    response = client.get("/documents/d1/file")
    assert response.status_code == 200
    body = response.json()
    assert "documents/d1/document.pdf" in body["url"]
    assert "response-content-type=application" in body["url"]
    assert body["expires_in"] == 300


def test_file_link_unknown_document_is_404(aws):
    assert client.get("/documents/nope/file").status_code == 404


def test_file_link_document_not_ready_is_409(aws):
    db.create_document("d1", "report.pdf")
    assert client.get("/documents/d1/file").status_code == 409