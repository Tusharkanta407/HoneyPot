# FastAPI app entry point
from fastapi import FastAPI

app = FastAPI(title="Honeypot AI")


@app.get("/")
def root():
    return {"status": "ok"}
