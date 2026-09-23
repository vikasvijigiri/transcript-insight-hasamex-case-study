"""Provider-neutral building blocks for evidence-first RAG retrieval.

The package deliberately has no database or model-SDK dependency.  Production
adapters can implement the protocols in :mod:`app.rag.retrieval`; the small
in-memory implementations make the pipeline deterministic and testable.
"""

from app.rag.chunking import TranscriptChunker
from app.rag.grounding import GroundingValidator
from app.rag.retrieval import HybridRetriever

__all__ = ["GroundingValidator", "HybridRetriever", "TranscriptChunker"]
