from winbot import llm


def test_uses_gemini_when_it_works(monkeypatch):
    monkeypatch.setattr(llm, "_gemini", lambda prompt: "from gemini")
    monkeypatch.setattr(llm, "_groq", lambda prompt: "from groq")
    assert llm.generate("hi") == ("from gemini", "gemini")


def test_falls_back_to_groq_when_gemini_fails(monkeypatch):
    def broken(prompt):
        raise RuntimeError("boom")

    monkeypatch.setattr(llm, "_gemini", broken)
    monkeypatch.setattr(llm, "_groq", lambda prompt: "from groq")
    assert llm.generate("hi") == ("from groq", "groq")