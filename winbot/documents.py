import logging
import tempfile
from pathlib import Path

from winbot import db, storage
from winbot.chunking import chunk_pages
from winbot.convert import CONVERTIBLE, convert_to_pdf
from winbot.overview import make_overview
from winbot.reader import read_pdf
from winbot.store import delete_chunks, store_chunks

SUPPORTED = CONVERTIBLE | {".pdf"}

logger = logging.getLogger("uvicorn.error")  # shows up in the API's own log


class UnsupportedFileType(ValueError):
    pass


class NoReadableText(ValueError):
    pass


def _cleanup(doc_id, chunk_count):
    """Undo whatever a failed upload stored. Never raises, so it can't hide the real error."""
    for undo in (
        lambda: storage.delete_document_files(doc_id),
        lambda: delete_chunks(doc_id, chunk_count),
    ):
        try:
            undo()
        except Exception:
            pass


def process_upload(path, doc_id=None):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise UnsupportedFileType(f"Unsupported file type: {suffix or '(none)'}")

    doc_id = doc_id or db.new_doc_id()
    db.create_document(doc_id, path.name)
    chunk_count = 0
    try:
        storage.upload_file(path, storage.original_key(doc_id, path.name))

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            pdf = path if suffix == ".pdf" else convert_to_pdf(path, tmp)
            storage.upload_file(pdf, storage.pdf_key(doc_id))
            pages = read_pdf(pdf)

        if not any(page["text"] for page in pages):
            raise NoReadableText(
                "No readable text found. Scanned documents are not supported yet."
            )

        chunks = chunk_pages(pages)
        chunk_count = len(chunks)
        store_chunks(doc_id, chunks)

        overview = {}
        try:
            overview = make_overview(doc_id, pages)
        except Exception:
            # The upload is still good without a summary and FAQ.
            logger.exception("Could not write the overview for %s", doc_id)

        return db.update_document(
            doc_id,
            status="ready",
            pages=len(pages),
            chunks=chunk_count,
            **overview,
        )
    except Exception as error:
        _cleanup(doc_id, chunk_count)
        db.update_document(doc_id, status="failed", error=str(error)[:300])
        raise