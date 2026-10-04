"""Shared clients for the local Chroma index and OpenAI.

The on-disk index lives at chroma_db/, collection "jet_lab". Those vectors were
embedded with all-MiniLM-L6-v2 (384 dimensions, unit length). Query embeddings
must use the same model. Chroma 1.5.9 wrote the index; older 0.6 clients cannot
open it.
"""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def refresh_env() -> None:
    """Re-read .env so a key added while the API is running takes effect."""
    load_dotenv(ROOT / ".env", override=True)


refresh_env()

os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")


def _resolve_chroma_path() -> str:
    raw = os.getenv("CHROMA_PATH", "./chroma_db")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return str(path.resolve())


CHROMA_PATH = _resolve_chroma_path()
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "jet_lab")
EMBED_MODEL = "all-MiniLM-L6-v2"
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.55"))
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def openai_configured() -> bool:
    refresh_env()
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def get_openai():
    from openai import OpenAI

    refresh_env()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to the .env file in the project root and restart the API."
        )
    return OpenAI(api_key=api_key)


@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def get_collection():
    import chromadb

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    return client.get_collection(name=CHROMA_COLLECTION)
