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
#
#
# def chunk_document(doc, chunk_size: int = 500, overlap: int = 80):
#     # TODO: produce list[{text, metadata}] suitable for embedding
#     raise NotImplementedError
#
#
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
