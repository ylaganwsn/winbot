import json

import boto3

from chunk_pdf import load_chunks

DOC_ID = "sample-cost-estimate"

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


chunks = load_chunks()

vectors = []
for i, chunk in enumerate(chunks):
    vectors.append(
        {
            "key": f"{DOC_ID}-{i}",
            "data": {"float32": embed(chunk["text"])},
            "metadata": {
                "doc_id": DOC_ID,
                "page": chunk["page"],
                "text": chunk["text"],
            },
        }
    )

s3vectors.put_vectors(
    vectorBucketName="winbot-vectors",
    indexName="winbot-chunks",
    vectors=vectors,
)

print(f"Stored {len(vectors)} vectors in winbot-chunks")