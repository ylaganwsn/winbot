from pathlib import Path

import boto3
import pytest

from winbot import config, db, documents
from winbot.documents import UnsupportedFileType

PAGES = [
    {"page": 1, "text": "RDS costs 5200 dollars per month."},
    {"page": 2, "text": "Savings of 400 dollars."},
]


def s3_keys():
    client = boto3.client("s3", region_name=config.REGION)
    response = client.list_objects_v2(Bucket="test-winbot-files")
    return sorted(item["Key"] for item in response.get("Contents", []))


@pytest.fixture
def fakes(monkeypatch):
    """Replace the slow or external parts: PDF reading, conversion and the vector store."""
    calls = {"stored": [], "deleted": [], "converted": []}

    monkeypatch.setattr(documents, "read_pdf", lambda path: PAGES)
    monkeypatch.setattr(
        documents, "store_chunks", lambda doc_id, chunks: calls["stored"].append((doc_id, chunks))
    )
    monkeypatch.setattr(
        documents, "delete_chunks", lambda doc_id, count: calls["deleted"].append((doc_id, count))
    )

    def fake_convert(path, outdir):
        calls["converted"].append(path.name)
        pdf = Path(outdir) / (path.stem + ".pdf")
        pdf.write_bytes(b"%PDF fake")
        return pdf

    monkeypatch.setattr(documents, "convert_to_pdf", fake_convert)
    return calls


def make_file(tmp_path, name, content=b"data"):
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_pdf_upload_is_processed_and_marked_ready(aws, fakes, tmp_path):
    record = documents.process_upload(make_file(tmp_path, "report.pdf"), doc_id="d1")

    assert record["status"] == "ready"
    assert record["pages"] == 2
    assert record["chunks"] == 2
    assert db.get_document("d1")["filename"] == "report.pdf"
    assert s3_keys() == ["documents/d1/document.pdf", "documents/d1/original/report.pdf"]
    assert fakes["converted"] == []
    doc_id, chunks = fakes["stored"][0]
    assert doc_id == "d1"
    assert [c["page"] for c in chunks] == [1, 2]


def test_word_upload_is_converted_and_both_files_are_kept(aws, fakes, tmp_path):
    documents.process_upload(make_file(tmp_path, "notes.docx"), doc_id="d1")

    assert fakes["converted"] == ["notes.docx"]
    assert s3_keys() == ["documents/d1/document.pdf", "documents/d1/original/notes.docx"]
    assert db.get_document("d1")["status"] == "ready"


def test_a_doc_id_is_generated_when_not_given(aws, fakes, tmp_path):
    record = documents.process_upload(make_file(tmp_path, "report.pdf"))
    assert len(record["doc_id"]) == 32


def test_unsupported_type_is_rejected_before_anything_is_created(aws, fakes, tmp_path):
    with pytest.raises(UnsupportedFileType):
        documents.process_upload(make_file(tmp_path, "malware.exe"))

    assert db.list_documents() == []
    assert s3_keys() == []


def test_document_without_text_fails_and_is_cleaned_up(aws, fakes, monkeypatch, tmp_path):
    monkeypatch.setattr(documents, "read_pdf", lambda path: [{"page": 1, "text": ""}])

    with pytest.raises(ValueError, match="No readable text"):
        documents.process_upload(make_file(tmp_path, "scan.pdf"), doc_id="d1")

    record = db.get_document("d1")
    assert record["status"] == "failed"
    assert "No readable text" in record["error"]
    assert s3_keys() == []
    assert fakes["stored"] == []


def test_failure_while_storing_vectors_removes_files_and_vectors(aws, fakes, monkeypatch, tmp_path):
    def broken(doc_id, chunks):
        raise RuntimeError("index unavailable")

    monkeypatch.setattr(documents, "store_chunks", broken)

    with pytest.raises(RuntimeError, match="index unavailable"):
        documents.process_upload(make_file(tmp_path, "report.pdf"), doc_id="d1")

    assert db.get_document("d1")["status"] == "failed"
    assert s3_keys() == []
    assert fakes["deleted"] == [("d1", 2)]


def test_cleanup_errors_do_not_hide_the_original_error(aws, fakes, monkeypatch, tmp_path):
    def broken_store(doc_id, chunks):
        raise RuntimeError("original problem")

    def broken_delete(doc_id, count):
        raise RuntimeError("cleanup problem")

    monkeypatch.setattr(documents, "store_chunks", broken_store)
    monkeypatch.setattr(documents, "delete_chunks", broken_delete)

    with pytest.raises(RuntimeError, match="original problem"):
        documents.process_upload(make_file(tmp_path, "report.pdf"), doc_id="d1")
        
OVERVIEW = {
    "summary": "It is about costs.",
    "faq": [{"question": "Which service costs most?", "answer": "RDS", "pages": [1]}],
    "suggestions": ["What are the savings?"],
}


def test_overview_is_saved_with_the_document(aws, fakes, monkeypatch, tmp_path):
    asked = []

    def fake_overview(doc_id, pages):
        asked.append((doc_id, pages, len(fakes["stored"])))
        return OVERVIEW

    monkeypatch.setattr(documents, "make_overview", fake_overview)
    record = documents.process_upload(make_file(tmp_path, "report.pdf"), doc_id="d1")

    assert record["summary"] == "It is about costs."
    assert record["faq"] == OVERVIEW["faq"]
    assert record["suggestions"] == ["What are the savings?"]
    assert db.get_document("d1")["faq"][0]["pages"] == [1]
    # it gets the document's pages, and only after the vectors are stored
    assert asked == [("d1", PAGES, 1)]


def test_a_failing_overview_does_not_fail_the_upload(aws, fakes, monkeypatch, tmp_path, caplog):
    def broken(doc_id, pages):
        raise RuntimeError("model down")

    monkeypatch.setattr(documents, "make_overview", broken)
    with caplog.at_level("ERROR", logger="uvicorn.error"):
        record = documents.process_upload(make_file(tmp_path, "report.pdf"), doc_id="d1")

    assert record["status"] == "ready"
    assert "summary" not in record and "faq" not in record
    assert "model down" in caplog.text
    assert s3_keys() == ["documents/d1/document.pdf", "documents/d1/original/report.pdf"]


def test_no_overview_is_requested_for_a_failed_upload(aws, fakes, monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(documents, "read_pdf", lambda path: [{"page": 1, "text": ""}])
    monkeypatch.setattr(documents, "make_overview", lambda doc_id, pages: called.append(doc_id))

    with pytest.raises(ValueError):
        documents.process_upload(make_file(tmp_path, "scan.pdf"), doc_id="d1")
    assert called == []