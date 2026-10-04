"""FastAPI entrypoint for the RAG lab UI.

  GET  /api/health
  GET  /api/corpus
  POST /api/retrieve   { "query": str } → { "chunks": [...], "latencyMs": int }
  POST /api/chat       { "query", "mode": "grounded"|"base", "chunk_ids": [str] }
                       → text/plain token stream

Run from the project root:

  uvicorn backend.api.main:app --reload --port 8000
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.models import CHROMA_COLLECTION, CHROMA_PATH, openai_configured
from backend.retrieval.rag import (
    NO_CONTEXT,
    chunks_by_ids,
    corpus_summary,
    generate_answer,
    retrieve,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Open the index and load the embedder before the first question.
    from backend.models import get_collection, get_embedder

    get_collection()
    get_embedder()
    yield


app = FastAPI(title="RAG JET Lab API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1)


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: str = "grounded"
    chunk_ids: list[str] | None = None


@app.get("/api/health")
def health():
    chroma_status = "ok"
    chunk_count = 0
    try:
        chunk_count = corpus_summary()["chunkCount"]
    except Exception as exc:
        chroma_status = str(exc)
    return {
        "status": "ok" if chroma_status == "ok" else "degraded",
        "chroma": chroma_status,
        "chunks": chunk_count,
        "collection": CHROMA_COLLECTION,
        "path": CHROMA_PATH,
        "openaiConfigured": openai_configured(),
    }


@app.get("/api/corpus")
def corpus():
    try:
        return corpus_summary()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Chroma index unavailable: {exc}") from exc


@app.post("/api/retrieve")
def api_retrieve(payload: RetrieveRequest):
    started = time.perf_counter()
    try:
        chunks = retrieve(payload.query.strip())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Retrieval failed: {exc}") from exc
    latency_ms = int((time.perf_counter() - started) * 1000)
    return {"chunks": chunks, "latencyMs": latency_ms}


@app.post("/api/chat")
def api_chat(payload: ChatRequest):
    query = payload.query.strip()
    mode = payload.mode
    if mode not in {"grounded", "base", "compare"}:
        raise HTTPException(status_code=400, detail="mode must be grounded, base, or compare")

    try:
        if mode == "base":
            chunks: list[dict] | None = []
        elif payload.chunk_ids is not None:
            chunks = chunks_by_ids(payload.chunk_ids)
        else:
            chunks = retrieve(query)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not load chunks: {exc}") from exc

    if mode != "base" and not chunks:
        return StreamingResponse(iter([NO_CONTEXT]), media_type="text/plain; charset=utf-8")

    if not openai_configured():
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not set. Add it to the .env file in the project root and restart the API.",
        )

    def token_stream():
        try:
            yield from generate_answer(query, mode, chunks)
        except Exception as exc:
            yield f"\n\nThe model request failed: {exc}"

    return StreamingResponse(token_stream(), media_type="text/plain; charset=utf-8")
