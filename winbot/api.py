import logging
import re
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from winbot import config, db, documents
from winbot.answer import answer as answer_question

logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Winbot")


class DocumentOut(BaseModel):
    doc_id: str
    filename: str
    status: str
    created_at: str
    pages: int | None = None
    chunks: int | None = None
    error: str | None = None


class HealthOut(BaseModel):
    status: str


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AnswerOut(BaseModel):
    answer: str
    pages: list[int]
    provider: str


class MessageOut(BaseModel):
    created_at: str
    question: str
    answer: str
    pages: list[int]
    provider: str


def _safe_filename(name):
    """Keep only a plain file name: no folders, no unusual characters."""
    name = Path((name or "").replace("\\", "/")).name
    name = re.sub(r"[^\w.\- ]", "_", name).strip(" .")
    return name


@app.get("/health", response_model=HealthOut)
def health():
    return {"status": "ok"}


@app.post("/documents", response_model=DocumentOut, status_code=201)
def upload_document(file: UploadFile = File(...)):
    filename = _safe_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in documents.SUPPORTED:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {suffix or '(none)'}. "
            f"Supported: {', '.join(sorted(documents.SUPPORTED))}",
        )

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        path = Path(tmp) / filename
        size = 0
        with open(path, "wb") as out:
            while block := file.file.read(1024 * 1024):
                size += len(block)
                if size > config.MAX_UPLOAD_BYTES:
                    limit_mb = config.MAX_UPLOAD_BYTES // (1024 * 1024)
                    raise HTTPException(
                        status_code=413, detail=f"File is larger than {limit_mb} MB."
                    )
                out.write(block)

        try:
            return documents.process_upload(path)
        except documents.UnsupportedFileType as error:
            raise HTTPException(status_code=415, detail=str(error))
        except documents.NoReadableText as error:
            raise HTTPException(status_code=422, detail=str(error))
        except Exception:
            logger.exception("Upload failed for %s", filename)
            raise HTTPException(
                status_code=500, detail="Processing failed. Try uploading again."
            )


@app.get("/documents", response_model=list[DocumentOut])
def list_documents():
    return db.list_documents()


@app.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str):
    document = db.get_document(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@app.post("/documents/{doc_id}/ask", response_model=AnswerOut)
def ask(doc_id: str, body: AskIn):
    document = db.get_document(doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document["status"] != "ready":
        raise HTTPException(status_code=409, detail="Document is not ready.")

    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question is empty.")

    try:
        result = answer_question(question, doc_id=doc_id)
    except Exception:
        logger.exception("Answering failed for document %s", doc_id)
        raise HTTPException(
            status_code=502, detail="Could not get an answer. Try again."
        )

    try:
        db.add_message(
            doc_id, question, result["answer"], result["pages"], result["provider"]
        )
    except Exception:
        logger.exception("Could not save chat history for document %s", doc_id)

    return result


@app.get("/documents/{doc_id}/messages", response_model=list[MessageOut])
def list_messages(doc_id: str):
    if db.get_document(doc_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return db.list_messages(doc_id)