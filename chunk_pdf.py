from pypdf import PdfReader

CHUNK_SIZE = 300
OVERLAP = 50


def clean(text):
    return " ".join(text.split())


def chunk_text(text, size, overlap):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


reader = PdfReader("sample-cost-estimate.pdf")
all_chunks = []
for number, page in enumerate(reader.pages, start=1):
    text = clean(page.extract_text())
    for piece in chunk_text(text, CHUNK_SIZE, OVERLAP):
        all_chunks.append({"page": number, "text": piece})

print("Total chunks:", len(all_chunks))
for i, chunk in enumerate(all_chunks):
    print(f"\n[{i}] page {chunk['page']} ({len(chunk['text'])} chars)")
    print(chunk["text"])