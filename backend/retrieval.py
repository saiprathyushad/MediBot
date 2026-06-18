"""
retrieval.py — Hybrid retrieval + reranking pipeline for MediBot.

Implements the two-stage retrieval pipeline taught in advanced_rag.ipynb:

  Stage 1 — Hybrid search (dense + BM25 via Qdrant):
    Fetches a broad candidate set (top-10) using Reciprocal Rank Fusion of
    dense semantic vectors and sparse BM25 keyword vectors, with an RBAC
    metadata filter applied inside Qdrant so restricted chunks never leave
    the vector store.

  Stage 2 — Cross-encoder reranking:
    Scores each candidate by reading the query and chunk text together
    (not independently), then keeps only the top-3 most relevant chunks.
    This removes noise before the LLM sees any context.

The build_retriever(role) function is called per-request so the RBAC
filter is always fresh and role-specific.
"""

import os
import pathlib
from dotenv import load_dotenv

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from langchain_community.cross_encoders import HuggingFaceCrossEncoder

from rbac import get_qdrant_filter

load_dotenv()

# Use URL mode (Docker / Qdrant Cloud) if QDRANT_URL is set in .env,
# otherwise fall back to the local on-disk path created by ingestion.py.
QDRANT_URL: str = os.getenv("QDRANT_URL", "")
QDRANT_LOCAL_PATH: str = str(pathlib.Path(__file__).parent / "qdrant_storage")
COLLECTION_NAME: str = "mediassist_docs"
EMBED_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

# ── Initialise embedding models (loaded once at module import) ────────────────

# Dense model — must match the model used during ingestion.
dense_embeddings = HuggingFaceEmbeddings(
    model_name=EMBED_MODEL,
    model_kwargs={"device": "cpu"},
    encode_kwargs={"normalize_embeddings": True},
)

# BM25 sparse model — must match the model used during ingestion.
sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25", batch_size=32)

# Lazy singleton — the vectorstore connection is opened on the FIRST request,
# not at module import time. This avoids a file-lock conflict when uvicorn's
# reloader imports the module before the worker process is fully started.
_vectorstore: QdrantVectorStore | None = None


def get_vectorstore() -> QdrantVectorStore:
    """Return the shared vectorstore, opening it on first call."""
    global _vectorstore
    if _vectorstore is None:
        kwargs = dict(
            embedding=dense_embeddings,
            sparse_embedding=sparse_embeddings,
            collection_name=COLLECTION_NAME,
            retrieval_mode=RetrievalMode.HYBRID,
        )
        if QDRANT_URL:
            kwargs["url"] = QDRANT_URL
        else:
            kwargs["path"] = QDRANT_LOCAL_PATH
        _vectorstore = QdrantVectorStore.from_existing_collection(**kwargs)
    return _vectorstore

# ── Cross-encoder reranker (loaded once — model is ~270 MB, downloads on first run) ──

# The cross-encoder reads query + chunk together, unlike bi-encoders that
# score them independently. This joint scoring is far more accurate for
# ranking but too slow to run over the full corpus — so we only run it on
# the top-10 candidates from hybrid search.
cross_encoder = HuggingFaceCrossEncoder(
    model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# Wraps the cross-encoder as a LangChain document compressor that
# re-orders candidates and keeps only the best top_n.
reranker = CrossEncoderReranker(model=cross_encoder, top_n=3)


def build_retriever(role: str) -> ContextualCompressionRetriever:
    """
    Build a per-request retriever that combines hybrid search + reranking
    with an RBAC filter scoped to the given role.

    Pipeline:
      1. broad_retriever queries Qdrant with k=10 and the role's RBAC filter.
         Both dense and sparse vectors are queried together inside Qdrant
         and fused with RRF — this is NOT two separate queries merged in code.
      2. ContextualCompressionRetriever applies the cross-encoder reranker
         to narrow the 10 candidates down to the 3 most relevant.

    The role-specific RBAC filter means chunks that this role cannot access
    are excluded inside Qdrant before any results reach Python.
    """
    qdrant_filter = get_qdrant_filter(role)

    # Stage 1: broad hybrid retrieval with RBAC filter.
    broad_retriever = get_vectorstore().as_retriever(
        search_kwargs={
            "k": 10,                    # fetch broad candidate set
            "filter": qdrant_filter,    # RBAC enforced at Qdrant level
        }
    )

    # Stage 2: wrap with cross-encoder reranker to narrow to top-3.
    return ContextualCompressionRetriever(
        base_compressor=reranker,
        base_retriever=broad_retriever,
    )
