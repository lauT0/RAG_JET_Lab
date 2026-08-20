# =============================================================================
# Backend — FastAPI RAG service (boilerplate)
#
# Intended layout:
#   api/         HTTP layer the React frontend calls (/api/chat, /api/retrieve)
#   ingestion/   Offline / admin pipeline: load → chunk → embed → index
#   retrieval/   Online path: query → retrieve chunks → build prompt → generate
#
# Keep notebook experiments in advanced_rag.ipynb until logic is stable, then
# move production code into these modules.
# =============================================================================

# Run later (once implemented):
#   uvicorn backend.api.main:app --reload --port 8000
