"""
main.py — FastAPI backend for MediBot.

Exposes four endpoints:
  POST /login                  — authenticate and receive a JWT
  POST /chat                   — main RAG endpoint (hybrid RAG or SQL RAG)
  GET  /collections/{role}     — list accessible collections for a role
  GET  /health                 — simple liveness check

/chat routing logic:
  1. Decode JWT to get the authenticated role.
  2. If the question looks analytical AND the role is billing_executive or admin
     → route to sql_rag_chain() (SQL RAG).
  3. Otherwise → hybrid retrieval (dense + BM25, RBAC-filtered, top-10)
     followed by cross-encoder reranking (top-3) and a Groq LLM answer.
  4. If hybrid retrieval returns zero chunks (all blocked by RBAC), return a
     friendly refusal message that names the role and its allowed collections —
     the LLM is never called in that case.

Every response includes: answer, sources, retrieval_type, role.
"""

import os
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain

from auth import authenticate_user, create_token, decode_token
from rbac import get_accessible_collections, is_sql_allowed
from retrieval import build_retriever
from sql_rag import sql_rag_chain

load_dotenv()

app = FastAPI(title="MediBot API", version="1.0.0")

# Allow requests from the Next.js dev server (localhost:3000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer()

# Groq LLM — shared instance for all hybrid RAG responses.
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_retries=2,
)

# System prompt for the hybrid RAG path.
# Strictly limits the LLM to the retrieved context to prevent hallucination,
# and asks it to name the source document in its answer.
MEDIBOT_SYSTEM_PROMPT: str = """You are MediBot, an internal knowledge assistant for MediAssist Health Network staff.
Answer the staff member's question using ONLY the information provided in the context below.
If the answer is not clearly stated in the context, say: "I don't have that information in the documents I can access."
Always mention which document or section your answer is based on.
Be concise, accurate, and professional.

Context:
{context}"""

# Keywords that signal an analytical/numbers question that should go to SQL RAG.
ANALYTICAL_KEYWORDS: list[str] = [
    "how many", "count", "total", "average", "sum", "number of",
    "list all claims", "list all tickets", "how much", "percentage",
    "which department", "top department", "most common", "breakdown",
]


# ── Pydantic request/response models ─────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: str
    username: str


class ChatRequest(BaseModel):
    question: str


class SourceCitation(BaseModel):
    source_document: str
    section_title: str
    collection: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    retrieval_type: str   # "hybrid_rag" or "sql_rag"
    role: str
    rbac_blocked: bool = False  # True when RBAC is the reason the question can't be answered


# ── Auth dependency ───────────────────────────────────────────────────────────

def get_current_role(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> tuple[str, str]:
    """
    FastAPI dependency: decode the Bearer JWT and return (username, role).
    Raises HTTP 401 if the token is missing, invalid, or expired.
    """
    try:
        payload = decode_token(credentials.credentials)
        return payload["sub"], payload["role"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── Helper ────────────────────────────────────────────────────────────────────

def is_analytical_question(question: str) -> bool:
    """
    Heuristic check: does this question look like a data/numbers query?
    If yes AND the role permits it, the /chat handler will use SQL RAG.
    """
    lower = question.lower()
    return any(kw in lower for kw in ANALYTICAL_KEYWORDS)


# Keywords that strongly signal a question is about a specific collection.
# Used to detect when a role is asking about content they can't access.
COLLECTION_KEYWORDS: dict[str, list[str]] = {
    "billing":   ["billing code", "insurance", "claim", "tpa", "pre-auth", "reimbursement",
                  "excl", "cashless", "insurer", "invoice", "icd code", "room rent",
                  "star health", "hdfc ergo", "icici lombard", "bajaj allianz"],
    "equipment": ["equipment", "calibration", "maintenance manual", "machine", "device manual",
                  "fault code", "service manual", "sterilisation"],
    "clinical":  ["drug formulary", "treatment protocol", "diagnostic reference",
                  "drug dosage", "prescription", "icd-10", "diagnosis code"],
    "nursing":   ["icu nursing", "infection control", "iv cannula", "nursing procedure",
                  "ventilator", "wound care"],
}

LLM_NO_ANSWER_PHRASES = [
    "i don't have that information",
    "not in the documents i can access",
    "not available in the provided",
    "the provided context does not",
    "the context does not",
    "not mentioned in the",
    "no information about",
]


def is_restricted_collection_question(question: str, role: str) -> bool:
    """
    Return True if the question is clearly about a collection the role
    cannot access. Used to show the RBAC warning card when the LLM
    correctly says it can't answer due to access restrictions.
    """
    accessible = get_accessible_collections(role)
    question_lower = question.lower()
    for collection, keywords in COLLECTION_KEYWORDS.items():
        if collection not in accessible:
            if any(kw in question_lower for kw in keywords):
                return True
    return False


def llm_could_not_answer(answer: str) -> bool:
    """Return True when the LLM's answer indicates it found no relevant info."""
    lower = answer.lower()
    return any(phrase in lower for phrase in LLM_NO_ANSWER_PHRASES)


def build_rbac_refusal(role: str) -> str:
    """
    Build a user-facing message explaining why no results were returned.
    Used when hybrid retrieval returns zero chunks due to RBAC filtering —
    this means the question was about a collection the role cannot access.
    """
    allowed = get_accessible_collections(role)
    allowed_str = ", ".join(allowed)
    return (
        f"As a {role.replace('_', ' ')}, you don't have access to the documents "
        f"needed to answer that question. I can only answer questions from the "
        f"{allowed_str} collections."
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    """Liveness probe — returns ok if the server is running."""
    return {"status": "ok"}


@app.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    """
    Authenticate a staff member with username and password.
    Returns a JWT that encodes the user's role, valid for 8 hours.
    The token must be passed as a Bearer header on all /chat requests.
    """
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(body.username, user["role"])
    return LoginResponse(token=token, role=user["role"], username=body.username)


@app.get("/collections/{role}")
def get_collections(role: str):
    """
    Return the list of document collections accessible to the given role.
    Used by the frontend sidebar to show the user what they can query.
    """
    collections = get_accessible_collections(role)
    if not collections:
        raise HTTPException(status_code=404, detail=f"Unknown role: {role}")
    return {"role": role, "collections": collections}


@app.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    user_info: tuple[str, str] = Depends(get_current_role),
):
    """
    Main RAG endpoint. Routes to SQL RAG or Hybrid RAG based on the question
    type and the authenticated user's role.

    Routing logic:
      - Analytical question + (billing_executive or admin) → SQL RAG
      - Everything else → Hybrid RAG (dense + BM25 + RBAC filter + reranking)
      - Zero chunks returned by hybrid retrieval → RBAC refusal message

    The RBAC filter is applied inside Qdrant — restricted chunks never reach
    the Python process, so an adversarial prompt cannot trick the LLM into
    revealing content from inaccessible collections.
    """
    username, role = user_info
    question = body.question

    # ── SQL RAG path ──────────────────────────────────────────────────────────
    if is_analytical_question(question) and is_sql_allowed(role):
        answer = sql_rag_chain(question)
        return ChatResponse(
            answer=answer,
            sources=[],                  # SQL answers come from the DB, not documents
            retrieval_type="sql_rag",
            role=role,
        )

    # ── Hybrid RAG path ───────────────────────────────────────────────────────

    # Build a per-request retriever with the RBAC filter for this role.
    # Stage 1: Qdrant hybrid search (top-10, RBAC-filtered).
    # Stage 2: CrossEncoder reranker narrows to top-3.
    retriever = build_retriever(role)

    # LangChain RAG chain: retriever → stuff documents → LLM.
    prompt = ChatPromptTemplate.from_messages([
        ("system", MEDIBOT_SYSTEM_PROMPT),
        ("human", "{input}"),
    ])
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    result = rag_chain.invoke({"input": question})
    retrieved_docs = result.get("context", [])

    # If no chunks were retrieved the RBAC filter blocked everything —
    # return a friendly, role-aware refusal without calling the LLM.
    if not retrieved_docs:
        return ChatResponse(
            answer=build_rbac_refusal(role),
            sources=[],
            retrieval_type="hybrid_rag",
            role=role,
            rbac_blocked=True,
        )

    # Build source citations from retrieved document metadata.
    sources: list[SourceCitation] = []
    seen = set()
    for doc in retrieved_docs:
        meta = doc.metadata
        key = (meta.get("source_document", ""), meta.get("section_title", ""))
        if key not in seen:
            seen.add(key)
            sources.append(SourceCitation(
                source_document=meta.get("source_document", "unknown"),
                section_title=meta.get("section_title", ""),
                collection=meta.get("collection", ""),
            ))

    answer = result["answer"]

    # Detect when the LLM couldn't answer because RBAC limits the visible docs.
    # The RBAC filter already blocked the restricted chunks at retrieval time;
    # this just ensures the UI shows the informative warning card.
    rbac_blocked = (
        llm_could_not_answer(answer)
        and is_restricted_collection_question(question, role)
    )
    if rbac_blocked:
        answer = build_rbac_refusal(role)
        sources = []

    return ChatResponse(
        answer=answer,
        sources=sources,
        retrieval_type="hybrid_rag",
        role=role,
        rbac_blocked=rbac_blocked,
    )
