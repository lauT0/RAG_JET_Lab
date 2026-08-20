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

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import StreamingResponse
#
# from backend.retrieval.rag import retrieve, generate_answer
#
# app = FastAPI(title="RAG JET Lab API")
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
#
# @app.get("/api/health")
# def health():
#     # TODO: confirm vector store / Ollama reachability
#     return {"status": "ok"}
#
#
# @app.post("/api/retrieve")
# async def api_retrieve(payload: dict):
#     # TODO:
#     #   1. Validate payload["query"]
#     #   2. Call retrieval.retrieve(query, top_k=...)
#     #   3. Return chunks with: id, title, sourceType, country, score, text
#     #   4. Include latencyMs for the inspector footer
#     raise NotImplementedError
#
#
# @app.post("/api/chat")
# async def api_chat(payload: dict):
#     # TODO:
#     #   1. Read mode: grounded | base | compare
#     #   2. For grounded: use chunk_ids / re-retrieve, build grounded prompt
#     #   3. For base: call LLM without corpus context
#     #   4. Stream tokens via StreamingResponse
#     #   5. Embed citation markers [1][2] aligned to returned chunk order
#     raise NotImplementedError
