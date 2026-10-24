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