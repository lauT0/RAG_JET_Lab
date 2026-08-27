"""
Chunking / indexing pipeline (boilerplate).

Move stable logic out of advanced_rag.ipynb into this module.

Suggested flow:
  load_documents → clean/normalize → chunk → embed → upsert_chroma

Where things should go:
  - Document loaders (PDF, TXT, future: HTML forum dumps, transcripts)
      → load_documents()
  - Text cleaning, language/region metadata tagging (Nigeria / Ghana)
      → normalize_document()
  - Chunking strategy (size, overlap, heading-aware splits)
      → chunk_document()
  - Embedding model (sentence_transformers today; keep swappable)
      → embed_chunks()
  - Vector store writes (Chroma collection + metadata: sourceType, country, title)
      → upsert_to_store()
  - CLI / admin entry for batch re-index of toy_rag_data/ or production corpus
      → run_ingestion()
"""

import re

from transformers import AutoTokenizer

# from pathlib import Path
#
#
# def load_documents(data_dir: Path):
#     # TODO: walk data_dir; parse PDF/TXT; attach source path + type guess
#     raise NotImplementedError
#
#
# def normalize_document(doc):
#     # TODO: strip boilerplate, normalize whitespace, attach country/sourceType
#     raise NotImplementedError

"""Chunking strategy:"""

_tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_MAX_TOKENS = 256
MIN_SENTENCE_TOKENS = 4


def count_tokens(text: str) -> int:
    return len(_tokenizer.encode(text, add_special_tokens=False)) #how many tokens in this string


def split_sentences(text: str) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s]
#splits sentences based on . ! and ?

def _merge_short_fragments(sentences: list[str], min_tokens: int = MIN_SENTENCE_TOKENS) -> list[str]:
    merged = []
    buffer = ""
    for sentence in sentences:
        buffer = f"{buffer} {sentence}".strip() if buffer else sentence
        if count_tokens(buffer) >= min_tokens:
            merged.append(buffer)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] = f"{merged[-1]} {buffer}"
        else:
            merged.append(buffer)
    return merged
# makes sure that short "sentences" aren't counted as their own chunks, but are merged into neighboring sentences instead

def _hard_split(sentence: str, chunk_size: int) -> list[str]:
    ids = _tokenizer.encode(sentence, add_special_tokens=False)
    return [_tokenizer.decode(ids[i:i + chunk_size]) for i in range(0, len(ids), chunk_size)]
#splits a long sentence into smaller chunks if it exceeds the chunk limit


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 25) -> list[str]: # try up to 500 to se what gets the best chunks
    chunk_size = min(chunk_size, EMBEDDING_MAX_TOKENS) #right now it is 256

    sentences = []
    for sentence in _merge_short_fragments(split_sentences(text)):
        if count_tokens(sentence) > chunk_size:
            sentences.extend(_hard_split(sentence, chunk_size))
        else:
            sentences.append(sentence)

    chunks = []
    current_sentences, current_len = [], 0

    for sentence in sentences:
        sentence_len = count_tokens(sentence)
        if current_sentences and current_len + sentence_len > chunk_size:
            chunk_str = " ".join(current_sentences)
            chunks.append(chunk_str)
            tail_ids = _tokenizer.encode(chunk_str, add_special_tokens=False)[-overlap:]
            overlap_text = _tokenizer.decode(tail_ids) if tail_ids else ""
            current_sentences = [overlap_text] if overlap_text else []
            current_len = len(tail_ids)
        current_sentences.append(sentence)
        current_len += sentence_len

    if current_sentences:
        chunks.append(" ".join(current_sentences))
    return chunks


def chunk_document(doc: dict, chunk_size: int = 200, overlap: int = 25) -> list[dict]:
    # doc = {"text": ..., "metadata": {...}} -- pairs each chunk with the doc's metadata + its index
    return [
        {"text": chunk, "metadata": {**doc["metadata"], "chunk_index": i}}
        for i, chunk in enumerate(chunk_text(doc["text"], chunk_size, overlap))
    ]


# def embed_chunks(chunks):
#     # TODO: call sentence_transformers (or API embedder); return vectors
#     raise NotImplementedError
#
#
# def upsert_to_store(chunks, embeddings, collection_name: str = "jet_lab"):
#     # TODO: write to chroma_db/ with ids + metadata used by the inspector UI
#     raise NotImplementedError
#
#
# def run_ingestion(data_dir: str = "toy_rag_data"):
#     # TODO: orchestrate the steps above; log counts for the corpus indicator
#     raise NotImplementedError
#
#
# if __name__ == "__main__":
#     run_ingestion()
