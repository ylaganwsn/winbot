from google import genai

client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3.5-flash-lite",
    input="In one sentence, what is RAG in AI?",
)

print(interaction.output_text)