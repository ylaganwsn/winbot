import json
import math

import boto3

client = boto3.client("bedrock-runtime", region_name="us-east-1")


def embed(text):
    response = client.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


question = "Which service costs the most?"

sentences = [
    "RDS is the most expensive service.",                 # expect: highest
    "The monthly estimate includes EC2, S3 and RDS.",     # expect: medium
    "The report was reviewed by the finance team.",       # expect: low
    "Bananas are rich in potassium.",                     # expect: lowest
]

question_vector = embed(question)
print("Question:", question)
for sentence in sentences:
    score = cosine_similarity(question_vector, embed(sentence))
    print(f"{score:.4f}  {sentence}")