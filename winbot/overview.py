import json
import re
from concurrent.futures import ThreadPoolExecutor

from winbot import config
from winbot.answer import answer
from winbot.llm import generate

SYSTEM = (
    "You help readers get started with a document. "
    "Using ONLY the document text provided, reply with JSON and nothing else, "
    'in exactly this shape: {"summary": "...", "questions": ["...", "..."]}. '
    "The summary is 2 or 3 plain sentences on what the document is about. "
    f"Write {config.FAQ_COUNT + config.SUGGESTION_COUNT} questions a reader would likely ask. "
    "Each must be short, specific, answerable from the document, and not a yes/no "
    "question. Do not number them."
)


def _document_text(pages):
    text = "\n\n".join(f"[Page {p['page']}]\n{p['text']}" for p in pages if p["text"])
    return text[: config.OVERVIEW_MAX_CHARS]


def _parse(text):
    """The model's JSON reply as (summary, questions). Raises ValueError if unusable."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("The overview reply was not valid JSON.") from error

    summary = data.get("summary") if isinstance(data, dict) else None
    questions = data.get("questions") if isinstance(data, dict) else None
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("The overview reply had no summary.")
    if not isinstance(questions, list):
        raise ValueError("The overview reply had no questions.")

    cleaned = []
    for question in questions:
        if isinstance(question, str):
            question = question.strip()[:300]
            if question and question not in cleaned:
                cleaned.append(question)
    return summary.strip(), cleaned


def _try_answer(doc_id, question):
    try:
        return answer(question, doc_id=doc_id)
    except Exception:
        return None


def make_overview(doc_id, pages):
    """A summary, ready-made answers and click-to-ask suggestions for one document.

    The document's chunks must already be stored, because each FAQ answer goes
    through the normal search-then-answer path. A question whose answer can't be
    found, or comes back without a source page, is left out.
    Raises if the summary itself can't be produced.
    """
    text, _ = generate(f"Document:\n{_document_text(pages)}", system=SYSTEM)
    summary, questions = _parse(text)

    candidates = questions[: config.FAQ_COUNT]
    suggestions = questions[config.FAQ_COUNT :][: config.SUGGESTION_COUNT]

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda q: _try_answer(doc_id, q), candidates))

    faq = [
        {"question": question, "answer": result["answer"], "pages": result["pages"]}
        for question, result in zip(candidates, results)
        if result and result["pages"]
    ]
    return {"summary": summary, "faq": faq, "suggestions": suggestions}