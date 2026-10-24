# Winbot

A chatbot that answers questions from an uploaded document, shows the source,
and says "I couldn't find that in this document." when the answer isn't there.

PDF works today. Word and other document formats are planned.

Portfolio project: RAG on AWS. Work in progress.

## How it works

1. The document is read and cut into overlapping chunks (word-safe), keeping track of where each chunk came from (page number for PDFs).
2. Amazon Titan Text Embeddings V2 (Bedrock, 1024 dimensions) turns each chunk into a vector.
3. The vectors are stored in Amazon S3 Vectors with the source page and text as metadata.
4. A question is embedded the same way and the closest chunks are retrieved.
5. Gemini answers using only those chunks. If Gemini fails, Groq answers instead.
6. If the best chunk is not similar enough, or the model finds no answer in the chunks,
   the bot says it couldn't find the answer, and no LLM is called in the first case.

## Layout

```
winbot/
  config.py       settings (region, bucket, models, thresholds)
  reader.py       document reading (PDF today)
  chunking.py     word-safe overlapping chunks
  embeddings.py   Titan embeddings
  store.py        store and search vectors in S3 Vectors
  llm.py          Gemini with Groq fallback
  answer.py       question -> answer flow
  ingest.py       load a document into the index
tests/            pytest tests (no AWS or API keys needed)
```

## Setup

Python 3.12, Windows PowerShell.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install boto3 "botocore[crt]" pypdf google-genai groq pytest
aws login
$env:GEMINI_API_KEY = "your-gemini-key"
$env:GROQ_API_KEY = "your-groq-key"
```

Keys are read from environment variables and are never stored in the repo.

## AWS resources (us-east-1)

Created by CLI for now; Terraform comes later. Everything is tagged `Project=winbot`.

```powershell
aws s3vectors create-vector-bucket --vector-bucket-name winbot-vectors --tags Project=winbot --region us-east-1
aws s3vectors create-index --vector-bucket-name winbot-vectors --index-name winbot-chunks --data-type float32 --dimension 1024 --distance-metric cosine --metadata-configuration nonFilterableMetadataKeys=text --tags Project=winbot --region us-east-1
```

## Usage

```powershell
python -m winbot.ingest sample-cost-estimate.pdf
python -m winbot.answer "Which service costs the most?"
python -m pytest -v
```

`sample-cost-estimate.pdf` is a fictional document made for testing.

## Known limitations

- Only PDF is supported so far.
- Search is not yet filtered by document, so only one document should be ingested at a time.
- On a very small index, S3 Vectors search can occasionally return fewer results than requested.
  Search over-fetches and keeps the best few to reduce the effect.
- The similarity threshold (0.15) is based on a handful of test questions.

## Open question

Word and text files have no fixed pages. How "show the source page" works for them
(convert to PDF for the viewer, or cite a section) is still to be decided.

## Roadmap

- More formats: Word (.docx), plain text and Markdown, with one reader per file type
- FastAPI backend and DynamoDB
- Streamlit UI: document viewer with jump-to-page and a floating chat
- Docker (two containers), ECS Fargate
- Terraform and GitHub Actions (OIDC)