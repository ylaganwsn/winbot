from winbot import answer as answer_module
from winbot import config


def fake_matches(*scores_and_pages):
    return [
        {"similarity": score, "page": page, "text": f"text on page {page}"}
        for score, page in scores_and_pages
    ]


def test_low_similarity_skips_the_llm(monkeypatch):
    monkeypatch.setattr(
        answer_module, "retrieve", lambda q, doc_id=None: fake_matches((0.04, 1))
    )

    def should_not_run(prompt):
        raise AssertionError("the LLM must not be called")

    monkeypatch.setattr(answer_module, "generate", should_not_run)

    result = answer_module.answer("anything")
    assert result == {"answer": config.NOT_FOUND, "pages": [], "provider": "none"}


def test_good_match_returns_answer_and_sorted_unique_pages(monkeypatch):
    monkeypatch.setattr(
        answer_module,
        "retrieve",
        lambda q, doc_id=None: fake_matches((0.30, 3), (0.20, 1), (0.18, 3)),
    )
    monkeypatch.setattr(answer_module, "generate", lambda p: ("Amazon RDS", "gemini"))

    result = answer_module.answer("Which service costs the most?")
    assert result == {"answer": "Amazon RDS", "pages": [1, 3], "provider": "gemini"}


def test_chunks_below_threshold_are_not_sent_to_the_llm(monkeypatch):
    monkeypatch.setattr(
        answer_module,
        "retrieve",
        lambda q, doc_id=None: fake_matches((0.30, 3), (0.05, 2)),
    )
    seen = {}

    def capture(prompt):
        seen["prompt"] = prompt
        return "ok", "gemini"

    monkeypatch.setattr(answer_module, "generate", capture)

    result = answer_module.answer("question")
    assert "text on page 3" in seen["prompt"]
    assert "text on page 2" not in seen["prompt"]
    assert result["pages"] == [3]


def test_llm_saying_not_found_returns_no_sources(monkeypatch):
    monkeypatch.setattr(
        answer_module, "retrieve", lambda q, doc_id=None: fake_matches((0.30, 3))
    )
    monkeypatch.setattr(
        answer_module,
        "generate",
        lambda p: ("I couldn't find that in this document.", "groq"),
    )

    result = answer_module.answer("What is the Azure cost?")
    assert result == {"answer": config.NOT_FOUND, "pages": [], "provider": "groq"}


def test_doc_id_is_passed_to_retrieve(monkeypatch):
    seen = {}

    def fake_retrieve(q, doc_id=None):
        seen["doc_id"] = doc_id
        return fake_matches((0.30, 1))

    monkeypatch.setattr(answer_module, "retrieve", fake_retrieve)
    monkeypatch.setattr(answer_module, "generate", lambda p: ("ok", "gemini"))

    answer_module.answer("question", doc_id="report")
    assert seen["doc_id"] == "report"


OVERVIEW = {"summary": "A bakery's opening notes.", "questions": ["Who is the head baker?"]}


def test_overview_lets_whole_document_questions_reach_the_llm(monkeypatch):
    monkeypatch.setattr(
        answer_module, "retrieve", lambda q, doc_id=None: fake_matches((0.04, 1))
    )
    seen = {}

    def capture(prompt, system):
        seen["prompt"], seen["system"] = prompt, system
        return "These are a bakery's opening notes.", "gemini"

    monkeypatch.setattr(answer_module, "generate", capture)

    result = answer_module.answer("Summarize this document", overview=OVERVIEW)
    assert result == {
        "answer": "These are a bakery's opening notes.",
        "pages": [],
        "provider": "gemini",
    }
    assert "A bakery's opening notes." in seen["prompt"]
    assert "- Who is the head baker?" in seen["prompt"]
    assert "(none matched this question)" in seen["prompt"]
    assert "text on page 1" not in seen["prompt"]
    assert seen["system"] == answer_module.OVERVIEW_SYSTEM


def test_overview_and_passages_are_sent_together(monkeypatch):
    monkeypatch.setattr(
        answer_module, "retrieve", lambda q, doc_id=None: fake_matches((0.30, 2))
    )
    seen = {}

    def capture(prompt, system):
        seen["prompt"] = prompt
        return "Marisol Vega", "gemini"

    monkeypatch.setattr(answer_module, "generate", capture)

    result = answer_module.answer("Who is the head baker?", overview=OVERVIEW)
    assert "[Page 2]" in seen["prompt"] and "Document overview" in seen["prompt"]
    assert result["pages"] == [2]


def test_overview_answer_can_still_be_not_found(monkeypatch):
    monkeypatch.setattr(answer_module, "retrieve", lambda q, doc_id=None: [])
    monkeypatch.setattr(
        answer_module, "generate", lambda p, s: (config.NOT_FOUND, "groq")
    )
    result = answer_module.answer("What is the weather?", overview=OVERVIEW)
    assert result == {"answer": config.NOT_FOUND, "pages": [], "provider": "groq"}