import sys

from winbot import config
from winbot.llm import generate
from winbot.store import retrieve


def answer(question):
    matches = [
        m for m in retrieve(question) if m["similarity"] >= config.SIMILARITY_THRESHOLD
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
    question = " ".join(sys.argv[1:]) or "Which service costs the most?"
    result = answer(question)
    print("Question:", question)
    print("Answer:", result["answer"])
    if result["pages"]:
        print("Sources: page", ", ".join(str(p) for p in result["pages"]))
    print("Answered by:", result["provider"])


if __name__ == "__main__":
    main()