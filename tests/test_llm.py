from winbot import llm


def test_uses_gemini_when_it_works(monkeypatch):
    monkeypatch.setattr(llm, "_gemini", lambda prompt, system: "from gemini")
    monkeypatch.setattr(llm, "_groq", lambda prompt, system: "from groq")
    assert llm.generate("hi") == ("from gemini", "gemini")


def test_falls_back_to_groq_when_gemini_fails(monkeypatch):
    def broken(prompt, system):
        raise RuntimeError("boom")

    monkeypatch.setattr(llm, "_gemini", broken)
    monkeypatch.setattr(llm, "_groq", lambda prompt, system: "from groq")
    assert llm.generate("hi") == ("from groq", "groq")


def test_custom_system_prompt_reaches_the_model(monkeypatch):
    seen = []
    monkeypatch.setattr(llm, "_gemini", lambda prompt, system: seen.append(system) or "ok")
    llm.generate("hi", system="be brief")
    llm.generate("hi")
    assert seen == ["be brief", llm.SYSTEM]