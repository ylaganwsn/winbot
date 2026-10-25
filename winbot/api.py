import re
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from winbot import config, db, documents

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