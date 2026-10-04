"""Retrieval and generation for the chatbot.

Online path:

  query
    → embed with all-MiniLM-L6-v2 (same model as the jet_lab index)
    → search Chroma
    → keep chunks whose cosine similarity is at least SIMILARITY_THRESHOLD
    → stream an OpenAI answer that cites those chunks as [1], [2], ...
"""

from __future__ import annotations

import os

from backend.models import (
    OPENAI_MODEL,
    SIMILARITY_THRESHOLD,
    get_collection,
    get_embedder,
    get_openai,
)

TOP_K = 5
CANDIDATES = 12

SOURCE_TYPE_MAP = {
    "Free Report": "report",
    "Open": "open",
    "Reference": "reference",
}

NO_CONTEXT = (
    "I could not find sufficiently relevant context in the curated corpus for this question. "
    "Try rephrasing, or ask about African tech, ICT, or entrepreneurship topics covered in the collection."
)

GROUNDED_SYSTEM = """You are a research assistant for a study of African technology, ICT, and entrepreneurship. The corpus is strongest on Nigeria, Ghana, and pan-African sources.

Rules:
- Answer only from the numbered context blocks.
- Cite the blocks you use inline, as [1], [2], and so on, matching the block numbers exactly.
- If the context does not contain the answer, say so. Do not fill gaps from general knowledge.
- Be specific. Prefer names, places, dates, and mechanisms that appear in the context."""

BASE_SYSTEM = """You answer questions from general knowledge, without a private document corpus.
Be direct. When you are generalizing, say so. Do not invent citations."""


def embed_query(query: str) -> list[float]:
    return get_embedder().encode(query).tolist()


def _cosine_from_l2(distance: float) -> float:
    # jet_lab vectors are unit length and the collection uses Chroma's default L2 space.
    return 1.0 - (distance * distance) / 2.0


def infer_country(metadata: dict, text: str) -> str:
    blob = " ".join(
        [
            str(metadata.get("title") or ""),
            str(metadata.get("source") or ""),
            text or "",
        ]
    ).lower()
    nigeria = sum(blob.count(word) for word in ("nigeria", "lagos", "abuja"))
    ghana = sum(blob.count(word) for word in ("ghana", "accra", "kumasi"))
    if nigeria and not ghana:
        return "Nigeria"
    if ghana and not nigeria:
        return "Ghana"
    return "Pan-African"


def present_chunk(chunk_id: str, text: str, metadata: dict | None, score: float) -> dict:
    metadata = metadata or {}
    raw_type = metadata.get("type") or "report"
    title = metadata.get("title") or str(metadata.get("source") or "Untitled")
    bounded = max(0.0, min(1.0, float(score)))
    return {
        "id": chunk_id,
        "title": title,
        "sourceType": SOURCE_TYPE_MAP.get(raw_type, str(raw_type).lower()),
        "country": infer_country(metadata, text or ""),
        "score": round(bounded, 4),
        "text": text or "",
    }


def search_store(query_embedding: list[float], top_k: int = CANDIDATES) -> list[dict]:
    result = get_collection().query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    chunks = []
    for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
        chunks.append(present_chunk(chunk_id, text, metadata, _cosine_from_l2(distance)))
    chunks.sort(key=lambda chunk: chunk["score"], reverse=True)
    return chunks


def filter_by_threshold(chunks: list[dict], threshold: float = SIMILARITY_THRESHOLD) -> list[dict]:
    return [chunk for chunk in chunks if chunk["score"] >= threshold]


def retrieve(query: str, top_k: int = TOP_K, filters: dict | None = None) -> list[dict]:
    # Country and source filters are applied in the inspector. `filters` is unused here.
    _ = filters
    embedding = embed_query(query)
    ranked = search_store(embedding, top_k=max(top_k, CANDIDATES))
    return filter_by_threshold(ranked)[:top_k]


def chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    got = get_collection().get(ids=chunk_ids, include=["documents", "metadatas"])
    by_id = {}
    for chunk_id, text, metadata in zip(got["ids"], got["documents"], got["metadatas"]):
        by_id[chunk_id] = present_chunk(chunk_id, text, metadata, score=1.0)
    return [by_id[chunk_id] for chunk_id in chunk_ids if chunk_id in by_id]


def build_prompt(query: str, chunks: list[dict]) -> str:
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        title = chunk.get("title") or "Untitled"
        blocks.append(f"[{index}] {title}\n{chunk['text']}")
    context = "\n\n".join(blocks)
    return (
        "Use only the context below to answer the question. "
        "Cite supporting blocks inline as [1], [2], and so on.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}"
    )


def _complete(messages: list[dict]):
    client = get_openai()
    return client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", OPENAI_MODEL),
        messages=messages,
        temperature=0.2,
        stream=True,
    )


def _yield_deltas(stream):
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def generate_base(query: str):
    stream = _complete(
        [
            {"role": "system", "content": BASE_SYSTEM},
            {"role": "user", "content": query},
        ]
    )
    yield from _yield_deltas(stream)


def generate_grounded(query: str, chunks: list[dict]):
    if not chunks:
        yield NO_CONTEXT
        return
    stream = _complete(
        [
            {"role": "system", "content": GROUNDED_SYSTEM},
            {"role": "user", "content": build_prompt(query, chunks)},
        ]
    )
    yield from _yield_deltas(stream)


def generate_answer(query: str, mode: str, chunks: list[dict] | None = None):
    if mode == "base":
        yield from generate_base(query)
        return
    if mode == "grounded":
        if chunks is None:
            chunks = retrieve(query)
        yield from generate_grounded(query, chunks)
        return
    if mode == "compare":
        raise ValueError("Call /api/chat twice for compare mode: once grounded, once base.")
    raise ValueError(f"Unknown mode: {mode}")


def corpus_summary() -> dict:
    collection = get_collection()
    got = collection.get(include=["metadatas"])
    sources = {
        (metadata or {}).get("source")
        for metadata in got["metadatas"]
        if metadata and metadata.get("source")
    }
    return {
        "documentCount": len(sources),
        "chunkCount": collection.count(),
        "regions": ["Nigeria", "Ghana", "Pan-African"],
        "collection": collection.name,
    }
