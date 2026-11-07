import argparse
import tempfile
from pathlib import Path

from winbot import db, storage
from winbot.overview import make_overview
from winbot.reader import read_pdf


def backfill_document(doc_id):
    """Write (or rewrite) the overview of one stored document. Returns its updated record."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        pdf = Path(tmp) / "document.pdf"
        storage.download_file(storage.pdf_key(doc_id), pdf)
        pages = read_pdf(pdf)
    return db.update_document(doc_id, **make_overview(doc_id, pages))


def documents_to_fill(doc_id=None, force=False):
    """Ready documents that have no overview yet (all ready ones with force)."""
    documents = db.list_documents()
    if doc_id:
        documents = [d for d in documents if d["doc_id"] == doc_id]
    return [
        d
        for d in documents
        if d["status"] == "ready" and (force or not d.get("summary"))
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Write the summary and FAQ for documents uploaded before that feature existed."
    )
    parser.add_argument("--doc", help="only this document ID")
    parser.add_argument(
        "--force", action="store_true", help="write it again even if one exists"
    )
    args = parser.parse_args()

    todo = documents_to_fill(args.doc, args.force)
    if not todo:
        print("Nothing to do.")
        return

    for document in todo:
        print(f"{document['filename']} ({document['doc_id']}) ... ", end="", flush=True)
        try:
            record = backfill_document(document["doc_id"])
        except Exception as error:
            print(f"failed: {type(error).__name__}: {str(error)[:200]}")
            continue

        print(
            f"done: {len(record['faq'])} ready answers, "
            f"{len(record['suggestions'])} suggestions"
        )
        print(f"  Summary: {record['summary']}")
        for item in record["faq"]:
            pages = ", ".join(str(p) for p in item["pages"])
            print(f"  FAQ: {item['question']} -> {item['answer']} (page {pages})")
        for question in record["suggestions"]:
            print(f"  Try: {question}")


if __name__ == "__main__":
    main()