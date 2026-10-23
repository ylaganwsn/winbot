import json
import sys

import boto3

bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
s3vectors = boto3.client("s3vectors", region_name="us-east-1")


def embed(text):
    response = bedrock.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}),
        contentType="application/json",
        accept="application/json",
    )
    return json.loads(response["body"].read())["embedding"]


question = " ".join(sys.argv[1:]) or "Which service costs the most?"

response = s3vectors.query_vectors(
    vectorBucketName="winbot-vectors",
    indexName="winbot-chunks",
    queryVector={"float32": embed(question)},
    topK=3,
    returnMetadata=True,
    returnDistance=True,
)

print("Question:", question)
for match in response["vectors"]:
    similarity = 1 - match["distance"]
    metadata = match["metadata"]
    print(f"\n{similarity:.4f}  page {metadata['page']}  ({match['key']})")
    print(metadata["text"][:120] + "...")