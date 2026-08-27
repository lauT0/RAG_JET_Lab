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

SIMILARITY_THRESHOLD = 0.55  # keep in sync with frontend MOCK.similarityThreshold for now
LLM_MODEL = "gpt-5.6-luna" 


from backend.models import client, rr_model, collection

def embed_query(query: str):
    # TODO: embed with the same model used in ingestion
    return client.embeddings.create(
        model="text-embedding-3-small",
        input=query
    ).data[0].embedding


def search_store(query, query_embedding, top_k: int = 5, filters: dict | None = None):
    # TODO: Chroma query; return ranked chunks with scores + metadata
    res_k = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=filters or {}
    )
    metadatas = res_k['metadatas'][0]
    ids = res_k['ids'][0]
    chunks = res_k['documents'][0]

    reranked = rr_model.rank(query=query, documents=chunks, return_documents=False, top_k=len(chunks))
    
    chunks = [
            {
                'id': ids[item['corpus_id']],
                'title': metadatas[item['corpus_id']]['title'],
                'sourceType': metadatas[item['corpus_id']]['sourceType'],
                'country': metadatas[item['corpus_id']]['country'],
                'text': chunks[item['corpus_id']],
                'score': item['score']
            }
            for item in reranked
        ]

    return chunks

#outputs list of dicts with keys 'id', 'title', 'sourceType', 'country', 'score', 'text'
def filter_by_threshold(chunks, threshold: float = SIMILARITY_THRESHOLD):
    # TODO: drop weak matches; empty list → UI "no relevant context found"
    filtered_chunks = [item for item in chunks if item['score'] >= threshold]
    
    return filtered_chunks

#Return chunks with: id, title, sourceType, country, score, text
def retrieve(query: str, top_k: int = 5, filters: dict | None = None):
    # TODO: embed_query → search_store → filter_by_threshold
    query_embedding = embed_query(query)
    chunks = search_store(query, query_embedding, top_k=top_k, filters=filters)
    filtered_chunks = filter_by_threshold(chunks, threshold=SIMILARITY_THRESHOLD)
    return filtered_chunks


#given chunks is the list of filtered chunks returned by retrieve()
def build_prompt(query: str, chunks: list):
    # TODO: numbered context blocks; ask model to cite with [1], [2], ...
    context_blocks = []
    for i, chunk in enumerate(chunks, start=1):
        context_blocks.append(f"[{i}] {chunk['text']}")
    context_str = "\n\n".join(context_blocks)
    prompt = f"Only use the following context to answer the question. If there is no context given, do not answer the question. If the context does not contain the answer, do not answer the question.\n\nContext: \n{context_str}\n\nQuestion: {query}"
    return prompt


def generate_base(query: str):
    # TODO: stream tokens from LLM with no retrieved context
    try:
        response = client.responses.create(
            model=LLM_MODEL,
            input=query,
        )
        return response.output_text
    except Exception as e:
        raise RuntimeError(f"LLM query failed: {e}")


def generate_grounded(query: str, chunks: list):
    # TODO: build_prompt → stream tokens from Ollama (or other provider)
    prompt = build_prompt(query, chunks) 
    try:
        response = client.responses.create(
            model=LLM_MODEL,
            input=prompt,
        )
        return response.output_text
    except Exception as e:
        raise RuntimeError(f"LLM query failed: {e}")


def generate_answer(query: str, mode: str, chunks: list | None = None):
    # TODO:
    #   mode == "base"      → generate_base
    #   mode == "grounded"  → retrieve if needed, then generate_grounded
    #   mode == "compare"   → API may call both paths; keep generators separate
    if mode == "base":
        return generate_base(query)
    elif mode == "grounded":
        if chunks is None:
            chunks = retrieve(query)
        return generate_grounded(query, chunks)
    elif mode == "compare":
        base_answer = generate_base(query)
        grounded_answer = generate_grounded(query, chunks or retrieve(query))
        return {"base": base_answer, "grounded": grounded_answer}
    else:
        raise ValueError(f"Unknown mode: {mode}")
