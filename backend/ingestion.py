"""
ingestion.py — Document ingestion pipeline for MediBot.

This script runs once (or whenever documents change) to parse all PDFs and
Markdown files in the mediassist_data folder, split them into
structure-aware chunks using Docling's HybridChunker, attach the required
RBAC metadata to every chunk, and index everything into a Qdrant collection
with both dense (semantic) and sparse (BM25) vectors for hybrid search.

Run as:  python ingestion.py
The script is idempotent — it deletes the existing collection first so
re-running it always produces a clean, up-to-date index.

Following the exact pattern from the course notebook (advanced_rag.ipynb):
  - DocumentConverter + HybridChunker for structural PDF/MD parsing
  - HuggingFaceEmbeddings for dense vectors
  - FastEmbedSparse (Qdrant/bm25) for sparse BM25 vectors
  - QdrantVectorStore.from_documents with RetrievalMode.HYBRID
"""

import os
import pathlib
import shutil
from dotenv import load_dotenv

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from transformers import AutoTokenizer
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from rbac import COLLECTION_ACCESS_ROLES

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────

# Local on-disk path — no Docker needed. Qdrant-client stores the index here.
# Set QDRANT_URL in .env to switch to a remote server (Docker or Qdrant Cloud).
QDRANT_URL: str | None = os.getenv("QDRANT_URL", "")
QDRANT_LOCAL_PATH: str = str(pathlib.Path(__file__).parent / "qdrant_storage")
COLLECTION_NAME: str = "mediassist_docs"

# Dense embedding model — same model used for both indexing and querying.
# all-MiniLM-L6-v2 is fast, produces 384-dim vectors, and works well for
# domain-adapted medical text after reranking.
EMBED_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

# Path to the data folder relative to this script's location.
DATA_ROOT: pathlib.Path = pathlib.Path(__file__).parent.parent.parent / "mediassist_data"

# Map each subfolder name to its collection identifier used in RBAC.
FOLDER_TO_COLLECTION: dict[str, str] = {
    "billing":  "billing",
    "clinical": "clinical",
    "equipment": "equipment",
    "general":  "general",
    "nursing":  "nursing",
}


# ── Helper: detect chunk type from Docling metadata ──────────────────────────

def detect_chunk_type(chunk) -> str:
    """
    Infer the chunk_type metadata field from Docling's chunk structure.
    Docling's DocChunk carries doc_items that describe whether the content
    is a table, heading, or regular paragraph.
    Returns one of: 'table', 'heading', 'text'.
    """
    if not chunk.meta or not chunk.meta.doc_items:
        return "text"
    # Check the label of the first doc_item in this chunk.
    item = chunk.meta.doc_items[0]
    label = str(item.label).lower() if hasattr(item, "label") else ""
    if "table" in label:
        return "table"
    if "heading" in label or "title" in label or "section" in label:
        return "heading"
    return "text"


# ── Main ingestion logic ──────────────────────────────────────────────────────

def load_and_chunk_collection(
    collection_name: str,
    folder: pathlib.Path,
    converter: DocumentConverter,
    chunker: HybridChunker,
) -> list[Document]:
    """
    Parse all files in a single collection folder and return a list of
    LangChain Documents with full RBAC metadata attached.

    Each chunk's page_content is produced by chunker.serialize(chunk), which
    automatically prepends the parent section heading — so the LLM always
    has context even when the raw paragraph text is short or ambiguous.
    """
    docs: list[Document] = []
    access_roles = COLLECTION_ACCESS_ROLES[collection_name]

    for file_path in sorted(folder.iterdir()):
        # Only process supported file types.
        if file_path.suffix.lower() not in (".pdf", ".md", ".markdown"):
            continue

        print(f"  Parsing: {file_path.name} ...")

        # Docling handles both PDF and Markdown with the same interface.
        dl_doc = converter.convert(str(file_path)).document

        # Chunk along the document's natural structure first, then by token
        # limit. merge_peers=True merges small sibling chunks under the same
        # heading to avoid orphaned micro-chunks.
        chunk_iter = chunker.chunk(dl_doc=dl_doc)

        for chunk in chunk_iter:
            # serialize() prepends the nearest parent heading to the chunk
            # text, giving every embedding full section context.
            page_content = chunker.serialize(chunk=chunk)

            # Extract the most specific section heading for citation display.
            section_title = ""
            if chunk.meta and chunk.meta.headings:
                section_title = chunk.meta.headings[-1]

            metadata = {
                "source_document": file_path.name,
                "collection": collection_name,
                # Stored as a list so Qdrant's MatchAny filter works directly.
                "access_roles": access_roles,
                "section_title": section_title,
                "chunk_type": detect_chunk_type(chunk),
            }

            docs.append(Document(page_content=page_content, metadata=metadata))

    print(f"  → {len(docs)} chunks from '{collection_name}'")
    return docs


def run_ingestion() -> None:
    """
    Main entry point: parse all collections, index into Qdrant.

    Steps:
    1. Initialise Docling converter and HybridChunker (aligned to embed model).
    2. Load and chunk every file across all 5 collections.
    3. Set up dense + sparse embedding models.
    4. Delete the existing Qdrant collection if present (idempotent re-run).
    5. Index all documents into a new collection with RetrievalMode.HYBRID,
       which stores both dense and sparse vectors in a single write pass.
    """

    print("=== MediBot Ingestion Pipeline ===\n")

    # Initialise Docling's converter and chunker.
    # The tokenizer must match the dense embedding model so that max_tokens
    # aligns with the model's context window — preventing truncation at query time.
    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL)
    converter = DocumentConverter()
    chunker = HybridChunker(
        tokenizer=tokenizer,
        max_tokens=128,    # same as notebook — keeps chunks concise
        merge_peers=True,  # avoids tiny orphaned chunks under the same heading
    )

    # Collect LangChain Documents from all collection folders.
    all_docs: list[Document] = []
    for folder_name, collection_name in FOLDER_TO_COLLECTION.items():
        folder = DATA_ROOT / folder_name
        if not folder.exists():
            print(f"  WARNING: folder not found — {folder}")
            continue
        print(f"\n[{collection_name}]")
        all_docs.extend(load_and_chunk_collection(collection_name, folder, converter, chunker))

    print(f"\nTotal chunks across all collections: {len(all_docs)}")

    # ── Embedding models (identical to notebook) ──────────────────────────────
    print("\nInitialising embedding models...")

    # Dense embeddings — captures semantic meaning.
    dense_embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"},          # use "cuda" if GPU available
        encode_kwargs={"normalize_embeddings": True},
    )

    # Sparse BM25 embeddings — captures exact keyword matches.
    # Critical for medical queries with precise drug names, ICD codes, etc.
    sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25", batch_size=32)

    # ── Wipe existing data so re-runs always start fresh ─────────────────────
    use_url = bool(QDRANT_URL)
    if use_url:
        # Server mode: delete collection via the API, then close before
        # from_documents() opens its own connection.
        print(f"\nUsing Qdrant server at {QDRANT_URL}")
        client = QdrantClient(url=QDRANT_URL)
        existing = [c.name for c in client.get_collections().collections]
        if COLLECTION_NAME in existing:
            print(f"Deleting existing collection '{COLLECTION_NAME}' for clean re-index...")
            client.delete_collection(COLLECTION_NAME)
        client.close()
    else:
        # Local mode: delete the storage folder entirely so no stale lock file
        # remains. Opening two QdrantClient instances on the same path causes
        # a portalocker conflict, so we wipe the folder here and let
        # from_documents() recreate it with a single fresh connection.
        print(f"\nUsing local Qdrant storage at {QDRANT_LOCAL_PATH}")
        if pathlib.Path(QDRANT_LOCAL_PATH).exists():
            print(f"Removing existing storage folder for clean re-index...")
            shutil.rmtree(QDRANT_LOCAL_PATH)

    # ── Index into Qdrant with hybrid mode ───────────────────────────────────
    # RetrievalMode.HYBRID tells QdrantVectorStore to store BOTH dense and
    # sparse vectors in one pass — not two separate indexes merged later.
    print(f"\nIndexing {len(all_docs)} chunks into Qdrant (this may take a few minutes)...")
    qdrant_kwargs = dict(
        documents=all_docs,
        embedding=dense_embeddings,
        sparse_embedding=sparse_embeddings,
        collection_name=COLLECTION_NAME,
        retrieval_mode=RetrievalMode.HYBRID,
    )
    if use_url:
        qdrant_kwargs["url"] = QDRANT_URL
    else:
        qdrant_kwargs["path"] = QDRANT_LOCAL_PATH

    vectorstore = QdrantVectorStore.from_documents(**qdrant_kwargs)

    location = f"{QDRANT_URL}/dashboard" if use_url else QDRANT_LOCAL_PATH
    print(f"\n✅ Ingestion complete. Collection '{COLLECTION_NAME}' ready.")
    print(f"   Location: {location}")
    return vectorstore


if __name__ == "__main__":
    run_ingestion()
