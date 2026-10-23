import json
import sys

import boto3
from google import genai

THRESHOLD = 0.15
MODEL = "gemini-3.5-flash-lite"
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


def answer(question):
    matches = [m for m in retrieve(question) if m["similarity"] >= THRESHOLD]
    if not matches:
        return NOT_FOUND, []

    context = "\n\n".join(f"[Page {m['page']}]\n{m['text']}" for m in matches)
    interaction = gemini.interactions.create(
        model=MODEL,
        system_instruction=SYSTEM,
        input=f"Context:\n{context}\n\nQuestion: {question}",
    )
    text = interaction.output_text.strip()

    if "find that in this document" in text.lower():
        return NOT_FOUND, []
    return text, sorted({m["page"] for m in matches})


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Which service costs the most?"
    text, pages = answer(question)
    print("Question:", question)
    print("Answer:", text)
    if pages:
        print("Sources: page", ", ".join(str(p) for p in pages))