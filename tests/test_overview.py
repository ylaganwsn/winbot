import json

import pytest

from winbot import config, overview

PAGES = [
    {"page": 1, "text": "Costs are 12,400 per month."},
    {"page": 2, "text": ""},
    {"page": 3, "text": "Savings come to 2,440."},
]
QUESTIONS = [f"Question {n}?" for n in range(1, 9)]


def reply(summary="It is about costs.", questions=QUESTIONS):
    return json.dumps({"summary": summary, "questions": questions})


@pytest.fixture
def fakes(monkeypatch):
    """Fake model and fake search-then-answer; records what they were given."""
    seen = {"prompts": [], "asked": []}

    def fake_generate(prompt, system):
        seen["prompts"].append((prompt, system))
        return reply(), "gemini"

    def fake_answer(question, doc_id=None):
        seen["asked"].append((question, doc_id))
        return {"answer": f"Answer to {question}", "pages": [1, 3], "provider": "gemini"}

    monkeypatch.setattr(overview, "generate", fake_generate)
    monkeypatch.setattr(overview, "answer", fake_answer)
    return seen


def test_parse_reads_plain_json():
    assert overview._parse(reply(questions=["A?", "B?"])) == ("It is about costs.", ["A?", "B?"])


def test_parse_accepts_json_wrapped_in_a_code_fence():
    fenced = "```json\n" + reply(questions=["A?"]) + "\n```"
    assert overview._parse(fenced) == ("It is about costs.", ["A?"])


def test_parse_cleans_blank_repeated_and_non_text_questions():
    text = reply(questions=["  A?  ", "", "A?", 5, None, "B?"])
    assert overview._parse(text)[1] == ["A?", "B?"]


@pytest.mark.parametrize(
    "text",
    [
        "not json at all",
        "[]",
        json.dumps({"questions": ["A?"]}),
        json.dumps({"summary": "  ", "questions": ["A?"]}),
        json.dumps({"summary": "ok"}),
        json.dumps({"summary": "ok", "questions": "A?"}),
    ],
)
def test_parse_rejects_unusable_replies(text):
    with pytest.raises(ValueError):
        overview._parse(text)


def test_document_text_labels_pages_and_skips_empty_ones():
    text = overview._document_text(PAGES)
    assert text == "[Page 1]\nCosts are 12,400 per month.\n\n[Page 3]\nSavings come to 2,440."


def test_document_text_is_cut_to_the_limit(monkeypatch):
    monkeypatch.setattr(config, "OVERVIEW_MAX_CHARS", 10)
    assert len(overview._document_text(PAGES)) == 10


def test_overview_splits_questions_into_faq_and_suggestions(fakes):
    result = overview.make_overview("d1", PAGES)

    assert result["summary"] == "It is about costs."
    assert [item["question"] for item in result["faq"]] == QUESTIONS[:5]
    assert result["faq"][0] == {
        "question": "Question 1?",
        "answer": "Answer to Question 1?",
        "pages": [1, 3],
    }
    assert result["suggestions"] == QUESTIONS[5:]
    assert sorted(fakes["asked"]) == sorted((q, "d1") for q in QUESTIONS[:5])


def test_overview_reads_the_document_with_its_own_instructions(fakes):
    overview.make_overview("d1", PAGES)
    prompt, system = fakes["prompts"][0]
    assert system == overview.SYSTEM
    assert "[Page 1]" in prompt and "Savings come to" in prompt


def test_faq_leaves_out_questions_with_no_answer_or_no_source(fakes, monkeypatch):
    def fake_answer(question, doc_id=None):
        if question == "Question 2?":
            return {"answer": config.NOT_FOUND, "pages": [], "provider": "none"}
        if question == "Question 3?":
            raise RuntimeError("model down")
        return {"answer": "ok", "pages": [1], "provider": "gemini"}

    monkeypatch.setattr(overview, "answer", fake_answer)
    result = overview.make_overview("d1", PAGES)
    assert [item["question"] for item in result["faq"]] == ["Question 1?", "Question 4?", "Question 5?"]
    assert result["suggestions"] == QUESTIONS[5:]


def test_suggestions_are_capped(fakes, monkeypatch):
    monkeypatch.setattr(overview, "generate", lambda prompt, system: (reply(questions=[f"Q{n}?" for n in range(20)]), "gemini"))
    result = overview.make_overview("d1", PAGES)
    assert len(result["faq"]) == config.FAQ_COUNT
    assert len(result["suggestions"]) == config.SUGGESTION_COUNT


def test_a_broken_overview_reply_raises(fakes, monkeypatch):
    monkeypatch.setattr(overview, "generate", lambda prompt, system: ("sorry, no", "gemini"))
    with pytest.raises(ValueError):
        overview.make_overview("d1", PAGES)
    assert fakes["asked"] == []