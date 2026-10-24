from pypdf import PdfReader


def clean(text):
    return " ".join(text.split())


def read_pdf(path):
    reader = PdfReader(path)
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        pages.append({"page": number, "text": clean(page.extract_text() or "")})
    return pages