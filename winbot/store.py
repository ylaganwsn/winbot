import boto3

from winbot import config
from winbot.embeddings import embed

_client = boto3.client("s3vectors", region_name=config.REGION)

BATCH_SIZE = 100


def store_chunks(doc_id, chunks):
    vectors = []
    for i, chunk in enumerate(chunks):
        vectors.append(
            {
                "key": f"{doc_id}-{i}",
                "data": {"float32": embed(chunk["text"])},
                "metadata": {
                    "doc_id": doc_id,
                    "page": chunk["page"],
                    "text": chunk["text"],
                },
            }
        )

    for start in range(0, len(vectors), BATCH_SIZE):
        _client.put_vectors(
            vectorBucketName=config.VECTOR_BUCKET,
            indexName=config.VECTOR_INDEX,
            vectors=vectors[start : start + BATCH_SIZE],
        )
    return len(vectors)


def retrieve(question, top_k=config.TOP_K, fetch_k=config.FETCH_K):
    response = _client.query_vectors(
        vectorBucketName=config.VECTOR_BUCKET,
        indexName=config.VECTOR_INDEX,
        queryVector={"float32": embed(question)},
        topK=fetch_k,
        returnMetadata=True,
        returnDistance=True,
    )
    results = [
        {
            "similarity": 1 - m["distance"],
            "page": m["metadata"]["page"],
            "text": m["metadata"]["text"],
        }
        for m in response["vectors"]
    ]
    results.sort(key=lambda m: m["similarity"], reverse=True)
    return results[:top_k]