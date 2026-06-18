"""
sql_rag.py — SQL RAG chain for MediBot analytical queries.

Implements sql_rag_chain(question) as a plain Python function with exactly
three explicit steps as required by the assignment:

  Step 1: Translate the natural language question into a SQL query using an LLM.
  Step 2: Clean the raw LLM output to extract only the SQL statement.
  Step 3: Execute the SQL against mediassist.db, then ask the LLM to produce
          a natural language answer from the result rows.

This function is only exposed to roles with analytical responsibilities:
billing_executive and admin. The RBAC check happens in main.py before
this function is ever called.

Pattern follows advanced_rag.ipynb exactly:
  - create_sql_query_chain for step 1
  - regex-based clean_sql for step 2
  - SQLDatabase.run + ChatPromptTemplate | llm for step 3
"""

import os
import re
import pathlib
from dotenv import load_dotenv

from langchain_community.utilities import SQLDatabase
from langchain_classic.chains import create_sql_query_chain
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# Path to the SQLite database provided with the assignment data.
DB_PATH: pathlib.Path = (
    pathlib.Path(__file__).parent.parent.parent / "mediassist_data" / "db" / "mediassist.db"
)

# ── Database and LLM setup (initialised once at module import) ────────────────

# LangChain's SQLDatabase wrapper — provides schema introspection and
# safe query execution. The schema is automatically included in the
# SQL generation prompt by create_sql_query_chain.
db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")

# Groq LLM — temperature=0 for deterministic SQL and factual answers.
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_retries=2,
)

# LangChain chain that generates SQL from a natural language question.
# It includes the database schema in its system prompt automatically so
# the LLM knows the available tables and columns.
sql_query_chain = create_sql_query_chain(llm, db)

# System prompt for the final answer step.
# Instructs the LLM to be concise and fact-based, not to hallucinate
# beyond what the SQL result contains.
ANSWER_SYSTEM_PROMPT: str = """You are MediAssist's data analytics assistant.
Given a user question and the raw SQL query result from the MediAssist database,
provide a clear, concise, and accurate natural language answer.
Be specific with all numbers and statistics from the data.
Do not invent figures that are not in the SQL result."""


def clean_sql(raw: str) -> str:
    """
    Step 2: Strip markdown code fences, 'SQLQuery:' prefixes, and any
    explanation text that the LLM may have prepended before the SQL.

    LLMs frequently wrap SQL in ```sql ... ``` fences or prefix it with
    'SQLQuery: SELECT ...' — executing such raw strings against sqlite3
    would raise a syntax error. This function isolates the pure SQL statement.
    """
    # Remove markdown code fences (```sql or plain ```).
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE)
    raw = raw.strip("`").strip()
    # If the LLM used 'SQLQuery:' or 'SQL:' labels, keep only what follows.
    for prefix in ("SQLQuery:", "SQL:", "Query:"):
        if prefix in raw:
            raw = raw.split(prefix)[-1].strip()
    return raw


def sql_rag_chain(question: str) -> str:
    """
    Answer an analytical question about the MediAssist database using SQL.

    Three explicit steps:
      1. LLM translates the NL question into a SQL SELECT statement.
      2. clean_sql() extracts the pure SQL from the LLM's raw output.
      3. Execute the SQL; pass the result rows back to the LLM for a
         natural language answer.

    Only call this for roles permitted to use SQL RAG (billing_executive,
    admin). The role check is enforced in the /chat endpoint before calling
    this function.
    """

    # ── Step 1: Translate question → SQL via LLM ─────────────────────────────
    # create_sql_query_chain includes the database schema in its prompt so
    # the LLM knows available tables (claims, maintenance_tickets) and columns.
    raw_sql: str = sql_query_chain.invoke({"question": question})
    print(f"[sql_rag] raw LLM output → {raw_sql!r}")

    # ── Step 2: Clean the raw output to isolate the SQL statement ─────────────
    sql: str = clean_sql(raw_sql)
    print(f"[sql_rag] cleaned SQL → {sql}")

    # ── Step 3: Execute SQL → pass result to LLM for NL answer ───────────────
    result: str = db.run(sql)
    print(f"[sql_rag] query result → {result!r}")

    answer_prompt = ChatPromptTemplate.from_messages([
        ("system", ANSWER_SYSTEM_PROMPT),
        ("human", "Question: {question}\nSQL Result: {result}\n\nAnswer:"),
    ])
    response = (answer_prompt | llm).invoke({
        "question": question,
        "result": result,
    })
    return response.content
