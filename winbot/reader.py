import tempfile
from pathlib import Path

from pypdf import PdfReader

from winbot.convert import CONVERTIBLE, convert_to_pdf


def clean(text):
    return " ".join(text.split())


def read_pdf(path):
    reader = PdfReader(path)
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        pages.append({"page": number, "text": clean(page.extract_text() or "")})
    return pages


def read_document(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix in CONVERTIBLE:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            return read_pdf(convert_to_pdf(path, tmp))
    raise ValueError(f"Unsupported file type: {suffix or '(none)'}")