"""
Retrieval + generation path for the chatbot (boilerplate).

Online request path (called from backend.api.main):

  query
    → retrieve()          # embed query, search Chroma, filter by threshold
    → build_prompt()      # inject ranked chunks; instruct citation markers
    → generate_answer()   # Ollama / OpenAI; stream tokens to the client

Where things should go:
  - Query embedding (same model as ingestion)
      → embed_query()
  - Vector search + optional metadata filters (country, sourceType)
      → search_store()
  - Score thresholding ("no relevant context found" when empty)
      → filter_by_threshold()
  - Prompt template for culturally-grounded answers + [n] citations
      → build_prompt()
  - Base-model path (no corpus) for Compare / Base modes
      → generate_base()
  - Grounded path with streaming
      → generate_grounded()
"""

# SIMILARITY_THRESHOLD = 0.55  # keep in sync with frontend MOCK.similarityThreshold for now
#
#
# def embed_query(query: str):
#     # TODO: embed with the same model used in ingestion
#     raise NotImplementedError
#
#
# def search_store(query_embedding, top_k: int = 5, filters: dict | None = None):
#     # TODO: Chroma query; return ranked chunks with scores + metadata
#     raise NotImplementedError
#
#
# def filter_by_threshold(chunks, threshold: float = SIMILARITY_THRESHOLD):
#     # TODO: drop weak matches; empty list → UI "no relevant context found"
#     raise NotImplementedError
#
#
# def retrieve(query: str, top_k: int = 5, filters: dict | None = None):
#     # TODO: embed_query → search_store → filter_by_threshold
#     raise NotImplementedError
#
#
# def build_prompt(query: str, chunks: list):
#     # TODO: numbered context blocks; ask model to cite with [1], [2], ...
#     raise NotImplementedError
#
#
# def generate_base(query: str):
#     # TODO: stream tokens from LLM with no retrieved context
#     raise NotImplementedError
#
#
# def generate_grounded(query: str, chunks: list):
#     # TODO: build_prompt → stream tokens from Ollama (or other provider)
#     raise NotImplementedError
#
#
# def generate_answer(query: str, mode: str, chunks: list | None = None):
#     # TODO:
#     #   mode == "base"      → generate_base
#     #   mode == "grounded"  → retrieve if needed, then generate_grounded
#     #   mode == "compare"   → API may call both paths; keep generators separate
#     raise NotImplementedError
