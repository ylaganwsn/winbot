import sys

import pytest

from winbot import backfill, db, storage

PAGES = [{"page": 1, "text": "RDS costs 5200 dollars."}]
OVERVIEW = {
    "summary": "It is about costs.",
    "faq": [{"question": "Which costs most?", "answer": "RDS", "pages": [1]}],
    "suggestions": ["What are the savings?"],
}


def add_document(doc_id, status="ready", **fields):
    db.create_document(doc_id, f"{doc_id}.pdf", status=status)
    if fields:
        db.update_document(doc_id, **fields)


@pytest.fixture
def fakes(monkeypatch):
    seen = {"read": [], "made": []}

    def fake_read(path):
        seen["read"].append(path.read_bytes())
        return PAGES

    def fake_make(doc_id, pages):
        seen["made"].append((doc_id, pages))
        return OVERVIEW

    monkeypatch.setattr(backfill, "read_pdf", fake_read)
    monkeypatch.setattr(backfill, "make_overview", fake_make)
    return seen


def put_pdf(tmp_path, doc_id, content=b"%PDF stored"):
    source = tmp_path / f"{doc_id}.pdf"
    source.write_bytes(content)
    storage.upload_file(source, storage.pdf_key(doc_id))


def test_backfill_reads_the_stored_pdf_and_saves_the_overview(aws, fakes, tmp_path):
    add_document("d1")
    put_pdf(tmp_path, "d1")

    record = backfill.backfill_document("d1")

    assert fakes["read"] == [b"%PDF stored"]
    assert fakes["made"] == [("d1", PAGES)]
    assert record["summary"] == "It is about costs."
    assert db.get_document("d1")["faq"] == OVERVIEW["faq"]
    assert db.get_document("d1")["status"] == "ready"


def test_only_ready_documents_without_an_overview_are_selected(aws):
    add_document("new")
    add_document("done", summary="Already has one.")
    add_document("broken", status="failed")
    add_document("busy", status="processing")

    assert [d["doc_id"] for d in backfill.documents_to_fill()] == ["new"]


def test_force_includes_documents_that_already_have_one(aws):
    add_document("new")
    add_document("done", summary="Already has one.")
    add_document("broken", status="failed")

    assert sorted(d["doc_id"] for d in backfill.documents_to_fill(force=True)) == ["done", "new"]


def test_one_document_can_be_picked_by_id(aws):
    add_document("a")
    add_document("b")
    assert [d["doc_id"] for d in backfill.documents_to_fill("b")] == ["b"]
    assert backfill.documents_to_fill("missing") == []


def run_main(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["backfill", *args])
    backfill.main()


def test_main_fills_documents_and_prints_what_it_wrote(aws, fakes, tmp_path, monkeypatch, capsys):
    add_document("d1")
    put_pdf(tmp_path, "d1")

    run_main(monkeypatch)

    out = capsys.readouterr().out
    assert "d1.pdf (d1) ... done: 1 ready answers, 1 suggestions" in out
    assert "Summary: It is about costs." in out
    assert "FAQ: Which costs most? -> RDS (page 1)" in out
    assert "Try: What are the savings?" in out
    assert db.get_document("d1")["summary"] == "It is about costs."


def test_main_says_so_when_there_is_nothing_to_do(aws, fakes, monkeypatch, capsys):
    add_document("done", summary="Already has one.")
    run_main(monkeypatch)
    assert capsys.readouterr().out.strip() == "Nothing to do."
    assert fakes["made"] == []


def test_one_failing_document_does_not_stop_the_others(aws, fakes, tmp_path, monkeypatch, capsys):
    add_document("a")  # its PDF is missing from storage, so it fails
    add_document("b")
    put_pdf(tmp_path, "b")

    run_main(monkeypatch)

    out = capsys.readouterr().out
    assert "failed:" in out
    assert "b.pdf (b) ... done" in out
    assert db.get_document("a").get("summary") is None
    assert db.get_document("b")["summary"] == "It is about costs."