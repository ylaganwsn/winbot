from winbot.chunking import chunk_pages, chunk_text

TEXT = " ".join(["alpha", "beta", "gamma", "RDS", "$5,200", "Multi-AZ"] * 40)


def test_empty_text_gives_no_chunks():
    assert chunk_text("", 300, 50) == []


def test_short_text_is_one_chunk():
    assert chunk_text("short text", 300, 50) == ["short text"]


def test_chunks_never_exceed_size():
    chunks = chunk_text(TEXT, 300, 50)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)


def test_chunks_never_cut_a_word():
    words = set(TEXT.split())
    for chunk in chunk_text(TEXT, 300, 50):
        assert set(chunk.split()) <= words


def test_chunks_overlap():
    chunks = chunk_text(TEXT, 300, 50)
    for first, second in zip(chunks, chunks[1:]):
        assert second.split()[0] in first.split()


def test_chunk_pages_keeps_page_numbers():
    pages = [
        {"page": 1, "text": "first page text"},
        {"page": 2, "text": TEXT},
    ]
    chunks = chunk_pages(pages)
    assert chunks[0] == {"page": 1, "text": "first page text"}
    assert {c["page"] for c in chunks} == {1, 2}