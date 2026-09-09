"""
FastAPI entrypoint (boilerplate).

Wire these endpoints to match the frontend contract in frontend/src/App.jsx:

  POST /api/retrieve
    body: { "query": str }
    resp: { "chunks": [...], "latencyMs": int }

  POST /api/chat
    body: { "query": str, "mode": "grounded"|"base"|"compare", "chunk_ids": [str] }
    resp: text/event-stream or chunked text (token stream)

When ready:
  1. Set USE_MOCK = false in frontend/src/App.jsx
  2. Uncomment the Vite proxy in frontend/vite.config.js
  3. Implement the handlers below (call into backend.retrieval)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.retrieval.rag import retrieve, generate_answer

app = FastAPI(title="RAG JET Lab API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    # TODO: confirm vector store / Ollama reachability
    try: 
      collection = client.get_collection(name="jet_lab")
      if collection is None or collection.count() == 0:
        return {"status": "error", "message": "Vector store unreachable: collection not found"}
      if collection.count() > 0:
        return {"status": "ok"} 
    except Exception as e:
      return {"status": "error", "message": f"Vector store unreachable: {e}"}

@app.post("/api/retrieve")
async def api_retrieve(payload: dict):
    # TODO:
    #   1. Validate payload["query"]
    #   2. Call retrieval.retrieve(query, top_k=...)
    #   3. Return chunks with: id, title, sourceType, country, score, text
    #   4. Include latencyMs for the inspector footer
    if payload is None or "query" not in payload:
        return {"error": "Missing 'query' in request body"}
    if payload["query"] == "":
        return {"error": "Query cannot be empty"}
    chunks = retrieve(payload["query"], top_k=5)
    raise NotImplementedError


@app.post("/api/chat")
async def api_chat(payload: dict):
    # TODO:
    #   1. Read mode: grounded | base | compare
    #   2. For grounded: use chunk_ids / re-retrieve, build grounded prompt
    #   3. For base: call LLM without corpus context
    #   4. Stream tokens via StreamingResponse
    #   5. Embed citation markers [1][2] aligned to returned chunk order
    
    if not isinstance(payload, dict):
      raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    query = payload.get("query")
    mode = payload.get("mode", "grounded")
    chunk_ids = payload.get("chunk_ids")

    if not isinstance(query, str) or not query.strip():
      raise HTTPException(status_code=400, detail="'query' must be a non-empty string")
    if mode not in {"grounded", "base", "compare"}:
      raise HTTPException(status_code=400, detail="'mode' must be grounded, base, or compare")
    if chunk_ids is not None and (
      not isinstance(chunk_ids, list)
      or not all(isinstance(chunk_id, str) for chunk_id in chunk_ids)
    ):
      raise HTTPException(status_code=400, detail="'chunk_ids' must be a list of strings")

    async def stream_response():
      chunks = None
      if mode != "base":
        chunks = retrieve(query)
        if chunk_ids:
          chunks_by_itextd = {chunk["id"]: chunk for chunk in chunks}
          chunks = [chunks_by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in chunks_by_id]

      result = generate_answer(query, mode, chunks)
      if isinstance(result, dict):
        text = (
          "Grounded answer:\n"
          f"{result['grounded']}\n\n"
          "Base answer:\n"
          f"{result['base']}"
        )
      else:
        text = result

      # Yield small text pieces so the browser receives a stream even when
      # the provider returns a complete response in one call.
      words = .split(" ")
      for index, word in enumerate(words):
        yield word + (" " if index < len(words) - 1 else "")

    return StreamingResponse(stream_response(), media_type="text/plain; charset=utf-8")
