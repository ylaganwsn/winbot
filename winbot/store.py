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


def retrieve(question, top_k=config.TOP_K, fetch_k=config.FETCH_K, doc_id=None):
    extra = {"filter": {"doc_id": doc_id}} if doc_id else {}
    response = _client.query_vectors(
        vectorBucketName=config.VECTOR_BUCKET,
        indexName=config.VECTOR_INDEX,
        queryVector={"float32": embed(question)},
        topK=fetch_k,
        returnMetadata=True,
        returnDistance=True,
        **extra,
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


def delete_chunks(doc_id, count):
    """Delete the vectors store_chunks wrote for a document (keys are <doc_id>-0 .. <doc_id>-N)."""
    keys = [f"{doc_id}-{i}" for i in range(count)]
    for start in range(0, len(keys), BATCH_SIZE):
        _client.delete_vectors(
            vectorBucketName=config.VECTOR_BUCKET,
            indexName=config.VECTOR_INDEX,
            keys=keys[start : start + BATCH_SIZE],
        )