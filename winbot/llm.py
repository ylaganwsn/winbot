from winbot import config

SYSTEM = (
    "You answer questions about a document using ONLY the context provided. "
    "If the context does not contain the answer, reply exactly: "
    f"{config.NOT_FOUND} "
    "Do not use outside knowledge. Keep answers short and factual."
)


def _gemini(prompt):
    from google import genai

    client = genai.Client()
    interaction = client.interactions.create(
        model=config.GEMINI_MODEL,
        system_instruction=SYSTEM,
        input=prompt,
    )
    return interaction.output_text.strip()


def _groq(prompt):
    from groq import Groq

    client = Groq()
    completion = client.chat.completions.create(
        model=config.GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    return completion.choices[0].message.content.strip()


def generate(prompt):
    try:
        return _gemini(prompt), "gemini"
    except Exception as error:
        print(f"[Gemini failed: {type(error).__name__}: {str(error)[:200]}. Trying Groq.]")
        return _groq(prompt), "groq"