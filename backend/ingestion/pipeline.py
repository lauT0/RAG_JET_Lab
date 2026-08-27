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

import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import chromadb
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer


def load_documents(data_dir: Path):
    # walk data_dir; parse PDF/TXT; attach source path + type guess
    docs = []
    for path in sorted(Path(data_dir).iterdir()):
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(path)
            text = " ".join(page.extract_text() for page in reader.pages if page.extract_text())
        elif path.suffix.lower() in (".txt", ".md"):
            text = path.read_text(encoding="utf-8")
        else:
            continue
        docs.append({"text": text, "metadata": {"source": str(path)}})
    return docs


@lru_cache(maxsize=None)
def _load_manifest(data_dir: str) -> dict:
    manifest_path = Path(data_dir) / "manifest.json"
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def normalize_document(doc):
    # strip boilerplate, normalize whitespace, attach country/sourceType from data_dir/manifest.json
    text = re.sub(r"\s+", " ", doc["text"]).strip()
    source = Path(doc["metadata"]["source"])
    manifest = _load_manifest(str(source.parent))
    metadata = {**doc["metadata"], **manifest.get(source.name, {})}
    return {"text": text, "metadata": metadata}

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


_embedder = SentenceTransformer("all-MiniLM-L6-v2")


def embed_chunks(chunks):
    # call sentence_transformers (or API embedder); return vectors
    return _embedder.encode([c["text"] for c in chunks]).tolist()


def upsert_to_store(chunks, embeddings, collection_name: str = "jet_lab"):
    # write to chroma_db/ with ids + metadata used by the inspector UI
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name=collection_name)
    ids = [f'{c["metadata"]["source"]}::{c["metadata"]["chunk_index"]}' for c in chunks]
    collection.upsert(
        documents=[c["text"] for c in chunks],
        embeddings=embeddings,
        metadatas=[c["metadata"] for c in chunks],
        ids=ids,
    )


def run_ingestion(data_dir: str = "rag_data", collection_name: str = "jet_lab"):
    # orchestrate the steps above; log counts for the corpus indicator
    docs = load_documents(data_dir)
    chunks = []
    for doc in docs:
        chunks += chunk_document(normalize_document(doc))

    embeddings = embed_chunks(chunks)
    upsert_to_store(chunks, embeddings, collection_name)

    counts = Counter(c["metadata"]["source"] for c in chunks)
    print(f"ingested {len(chunks)} chunks from {len(docs)} documents into '{collection_name}'")
    for source, n in counts.items():
        print(f"  {n:4d}  {source}")


if __name__ == "__main__":
    run_ingestion()
