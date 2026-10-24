from winbot import config


def chunk_text(text, size, overlap):
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            space = text.rfind(" ", start, end)
            if space > start:
                end = space
        chunks.append(text[start:end].strip())
        if end >= n:
            break
        next_start = end - overlap
        if next_start <= start:
            next_start = end
        space = text.find(" ", next_start, end)
        if space != -1:
            next_start = space + 1
        start = next_start
    return chunks


def chunk_pages(pages, size=config.CHUNK_SIZE, overlap=config.CHUNK_OVERLAP):
    chunks = []
    for page in pages:
        for piece in chunk_text(page["text"], size, overlap):
            chunks.append({"page": page["page"], "text": piece})
    return chunks