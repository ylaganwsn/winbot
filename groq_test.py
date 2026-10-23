from groq import Groq

client = Groq()

completion = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "user", "content": "In one sentence, what is RAG in AI?"},
    ],
)

print(completion.choices[0].message.content)