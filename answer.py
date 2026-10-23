import json
import sys

import boto3
from google import genai
from groq import Groq

THRESHOLD = 0.15
GEMINI_MODEL = "gemini-3.5-flash-lite"
GROQ_MODEL = "openai/gpt-oss-120b"
NOT_FOUND = "I couldn't find that in this document."

SYSTEM = (
    "You answer questions about a document using ONLY the context provided. "
    "If the context does not contain the answer, reply exactly: "
    f"{NOT_FOUND} "
    "Do not use outside knowledge. Keep answers short and factual."
)

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
s3vectors = boto3.client("s3vectors", region_name="us-east-1")
gemini = genai.Client()
groq = Groq()


def embed(text):
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def retrieve(question, top_k=3):
    response = s3vectors.query_vectors(
        vectorBucketName="winbot-vectors",
        indexName="winbot-chunks",
        queryVector={"float32": embed(question)},
        topK=top_k,
        returnMetadata=True,
        returnDistance=True,
    )
    return [
        {
            "similarity": 1 - m["distance"],
            "page": m["metadata"]["page"],
            "text": m["metadata"]["text"],
        }
        for m in response["vectors"]
    ]


def generate(prompt):
    try:
        interaction = gemini.interactions.create(
            model=GEMINI_MODEL,
            system_instruction=SYSTEM,
            input=prompt,
        )
        return interaction.output_text.strip(), "gemini"
    except Exception as error:
        print(f"[Gemini failed: {type(error).__name__}. Trying Groq.]")
        completion = groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        return completion.choices[0].message.content.strip(), "groq"


def answer(question):
    matches = [m for m in retrieve(question) if m["similarity"] >= THRESHOLD]
    if not matches:
        return NOT_FOUND, [], "none"

    context = "\n\n".join(f"[Page {m['page']}]\n{m['text']}" for m in matches)
    text, provider = generate(f"Context:\n{context}\n\nQuestion: {question}")

    if "find that in this document" in text.lower():
        return NOT_FOUND, [], provider
    return text, sorted({m["page"] for m in matches}), provider


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Which service costs the most?"
    text, pages, provider = answer(question)
    print("Question:", question)
    print("Answer:", text)
    if pages:
        print("Sources: page", ", ".join(str(p) for p in pages))
    print("Answered by:", provider)