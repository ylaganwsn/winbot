import argparse

from winbot import config
from winbot.llm import generate
from winbot.store import retrieve


def answer(question, doc_id=None):
    matches = [
        m
        for m in retrieve(question, doc_id=doc_id)
        if m["similarity"] >= config.SIMILARITY_THRESHOLD
    ]
    if not matches:
        return {"answer": config.NOT_FOUND, "pages": [], "provider": "none"}

    context = "\n\n".join(f"[Page {m['page']}]\n{m['text']}" for m in matches)
    text, provider = generate(f"Context:\n{context}\n\nQuestion: {question}")

    if "find that in this document" in text.lower():
        return {"answer": config.NOT_FOUND, "pages": [], "provider": provider}
    return {
        "answer": text,
        "pages": sorted({m["page"] for m in matches}),
        "provider": provider,
    }


def main():
    parser = argparse.ArgumentParser(description="Ask a question about a document.")
    parser.add_argument("question", nargs="*", help="the question to ask")
    parser.add_argument("--doc", help="only search this document ID")
    args = parser.parse_args()

    question = " ".join(args.question) or "Which service costs the most?"
    result = answer(question, doc_id=args.doc)
    print("Question:", question)
    print("Answer:", result["answer"])
    if result["pages"]:
        print("Sources: page", ", ".join(str(p) for p in result["pages"]))
    print("Answered by:", result["provider"])


if __name__ == "__main__":
    main()