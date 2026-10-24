import sys
from pathlib import Path

from winbot.chunking import chunk_pages
from winbot.reader import read_pdf
from winbot.store import store_chunks


def ingest(path):
    doc_id = Path(path).stem
    chunks = chunk_pages(read_pdf(path))
    count = store_chunks(doc_id, chunks)
    return doc_id, count


def main():
    if len(sys.argv) != 2:
        print("Usage: python -m winbot.ingest <file.pdf>")
        sys.exit(1)
    doc_id, count = ingest(sys.argv[1])
    print(f"Stored {count} chunks for '{doc_id}'")


if __name__ == "__main__":
    main()