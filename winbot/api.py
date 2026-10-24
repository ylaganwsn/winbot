from fastapi import FastAPI

app = FastAPI(title="Winbot")


@app.get("/health")
def health():
    return {"status": "ok"}