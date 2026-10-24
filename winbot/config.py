import os

REGION = "us-east-1"

EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
EMBED_DIMENSIONS = 1024

VECTOR_BUCKET = "winbot-vectors"
VECTOR_INDEX = "winbot-chunks"

DOCUMENTS_TABLE = "winbot-documents"
MESSAGES_TABLE = "winbot-messages"

GEMINI_MODEL = "gemini-3.5-flash-lite"
GROQ_MODEL = "openai/gpt-oss-120b"

CHUNK_SIZE = 300
CHUNK_OVERLAP = 50

TOP_K = 3
FETCH_K = 10
SIMILARITY_THRESHOLD = 0.15

NOT_FOUND = "I couldn't find that in this document."


def files_bucket():
    name = os.environ.get("WINBOT_FILES_BUCKET")
    if not name:
        raise RuntimeError(
            "Set the WINBOT_FILES_BUCKET environment variable to the files bucket name."
        )
    return name