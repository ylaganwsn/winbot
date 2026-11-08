import argparse

from winbot import config
from winbot.llm import generate
from winbot.store import retrieve


OVERVIEW_SYSTEM = (
    "You answer questions about one document. You are given an overview of the "
    "whole document and, when found, passages from it. "
    "Use the passages for specific facts. "
    "Use the overview for questions about the document as a whole, such as what "
    "it is about, a summary, or an explanation of it. "
    "If the user asks how you can help or what you can do, say that you answer "
    "questions about this document and give two or three of the example questions. "
    "Use ONLY the overview and passages, never outside knowledge. "
    "If they do not contain the answer, reply exactly: "
    f"{config.NOT_FOUND} "
    "Keep answers short and factual."
)


def _overview_text(overview):
    lines = [f"Document overview:\n{overview['summary']}"]
    if overview.get("questions"):
        examples = "\n".join(f"- {q}" for q in overview["questions"])
        lines.append(f"Example questions this document answers:\n{examples}")
    return "\n\n".join(lines)


def answer(question, doc_id=None, overview=None):
    """Answer from the best matching passages, plus the document's overview if given.

    overview is {"summary": str, "questions": [str]}; with it, questions about the
    whole document ("what is this about?") can be answered too.
    """
    matches = [
        m
        for m in retrieve(question, doc_id=doc_id)
        if m["similarity"] >= config.SIMILARITY_THRESHOLD
    ]
    if not matches and not overview:
        return {"answer": config.NOT_FOUND, "pages": [], "provider": "none"}

    context = "\n\n".join(f"[Page {m['page']}]\n{m['text']}" for m in matches)
    if overview:
        prompt = (
            f"{_overview_text(overview)}\n\n"
            f"Passages:\n{context or '(none matched this question)'}\n\n"
            f"Question: {question}"
        )
        text, provider = generate(prompt, OVERVIEW_SYSTEM)
    else:
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