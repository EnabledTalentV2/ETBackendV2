import re
from typing import Optional, Dict, Any, List

from django.conf import settings
from django.shortcuts import get_object_or_404

from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from openai import OpenAI

from candidates.models import CandidateProfile

client = OpenAI()

# ============================================================
# PROD GUARDRAILS CONFIG
# ============================================================

ALLOWED_TABLES = {"candidates_candidateprofile"}

ALLOWED_COLUMNS = {
    "slug",
    "resume_data",
    "willing_to_relocate",
    "employment_type_preferences",
    "work_mode_preferences",
    "has_workvisa",
    "disability_categories",
    "accommodation_needs",
    "disclosure_preference",
    "workplace_accommodations",
    "expected_salary_range",
    "is_available",
}

FORBIDDEN_SQL_PATTERNS = [
    # Block FTS completely
    r"\bto_tsvector\b",
    r"\bto_tsquery\b",
    r"\b@@\b",
    r"\bplainto_tsquery\b",
    r"\bphraseto_tsquery\b",
    r"\bwebsearch_to_tsquery\b",
    # Block writes
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\btruncate\b",
    r"\bcreate\b",
]

MAX_LIMIT = 20
DEFAULT_LIMIT = 10
POSTGRES_STATEMENT_TIMEOUT_MS = 5000


# ============================================================
# SQL PROMPT (FORCE TOOL USAGE)
# ============================================================
SQL_PREFIX = """
You are a STRICT SQL agent.

MANDATORY:
- You MUST call the tool `safe_sql_query`
- You MUST generate ONE SELECT query
- Query ONLY candidates_candidateprofile
- ALWAYS include slug
- ALWAYS filter is_available = TRUE
- LIMIT 10–20 rows

CRITICAL:
- resume_data is JSON
- Search ONLY using:
  resume_data::text ILIKE '%keyword%'
- NEVER use full-text search
- NEVER invent columns

Return SQL ONLY.
"""


# ============================================================
# DB HELPERS
# ============================================================
def build_db_url_from_django_settings() -> str:
    db = settings.DATABASES["default"]
    engine = db["ENGINE"]

    if "sqlite" in engine:
        return f"sqlite:///{db['NAME']}"

    return (
        f"postgresql://{db['USER']}:{db['PASSWORD']}"
        f"@{db['HOST']}:{db.get('PORT', 5432)}/{db['NAME']}?sslmode=require"
    )


def is_sqlite() -> bool:
    return "sqlite" in settings.DATABASES["default"]["ENGINE"].lower()


def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql.strip())


# ============================================================
# SQL PARSING / GUARDRAILS
# ============================================================
def _extract_referenced_tables(sql: str) -> List[str]:
    sql_l = sql.lower()
    tables = set()

    for kw in (" from ", " join "):
        for part in sql_l.split(kw)[1:]:
            token = part.strip().split()[0].replace('"', "").split(".")[-1]
            tables.add(token.rstrip(","))

    return list(tables)


def _extract_selected_columns(sql: str) -> List[str]:
    select_part = sql.lower().split("from")[0]
    cols = select_part.replace("select", "").split(",")

    cleaned = []
    for c in cols:
        c = c.strip().split(" as ")[0].split(".")[-1]
        if c != "*":
            cleaned.append(c)

    return cleaned


def _enforce_limit(sql: str) -> str:
    if "limit" not in sql.lower():
        return f"{sql} LIMIT {DEFAULT_LIMIT}"

    limit = int(re.search(r"\blimit\s+(\d+)", sql.lower()).group(1))
    if limit > MAX_LIMIT:
        return re.sub(r"\blimit\s+\d+", f"LIMIT {MAX_LIMIT}", sql, flags=re.I)

    return sql


def validate_and_sanitize_sql(sql: str) -> str:
    if not sql.lower().startswith("select"):
        raise ValueError("Only SELECT allowed")

    if ";" in sql.strip().rstrip(";"):
        raise ValueError("Multiple statements blocked")

    for pat in FORBIDDEN_SQL_PATTERNS:
        if re.search(pat, sql, re.I):
            raise ValueError(f"Forbidden SQL detected: {pat}")

    tables = _extract_referenced_tables(sql)
    for t in tables:
        if t not in ALLOWED_TABLES:
            raise ValueError(f"Table not allowed: {t}")

    cols = _extract_selected_columns(sql)
    for c in cols:
        if c not in ALLOWED_COLUMNS:
            raise ValueError(f"Column not allowed: {c}")

    sql = _enforce_limit(sql)

    if "is_available" not in sql.lower():
        sql += " AND is_available = TRUE" if "where" in sql.lower() else " WHERE is_available = TRUE"

    # 🔥 SQLite compatibility fixes
    if is_sqlite():
        sql = re.sub(r"\bilike\b", "LIKE", sql, flags=re.I)
        sql = re.sub(r"::text", "", sql, flags=re.I)

    return _normalize_sql(sql)


# ============================================================
# SAFE SQL TOOL
# ============================================================
def _get_sql_db() -> SQLDatabase:
    uri = build_db_url_from_django_settings()
    args = {}

    if uri.startswith("postgresql://"):
        args["connect_args"] = {
            "options": f"-c statement_timeout={POSTGRES_STATEMENT_TIMEOUT_MS}"
        }

    return SQLDatabase.from_uri(uri, engine_args=args)


@tool("safe_sql_query")
def safe_sql_query(sql: str) -> str:
    """
    Execute a validated, read-only SQL SELECT query against the candidates database.
    The query is strictly guarded: no writes, no schema changes, and limited results.
    """
    sql = validate_and_sanitize_sql(sql)
    return _get_sql_db().run(sql)


# ============================================================
# PUBLIC API
# ============================================================
def query_candidates(query: str) -> Dict[str, Any]:
    llm = ChatOpenAI(model="gpt-5-mini")

    agent = create_react_agent(
        llm,
        tools=[safe_sql_query],
        prompt=SystemMessage(content=SQL_PREFIX),
    )

    result = agent.invoke({"messages": [HumanMessage(content=query)]})

    outputs = [m.content for m in result["messages"] if isinstance(m, ToolMessage)]

    if not outputs:
        return {"raw_results": [], "processed_summary": "No results found."}

    mentor_prompt = f"""
You are LYRA — a friendly career mentor.

User Query:
{query}

Results:
{outputs}

Explain strengths, gaps, projects, and upskilling.
End with: "If you'd like, I can build a custom roadmap."
"""

    summary = client.chat.completions.create(
        model="gpt-5",
        messages=[{"role": "system", "content": mentor_prompt}],
    ).choices[0].message.content

    return {"raw_results": outputs, "processed_summary": summary}


# ============================================================
# CANDIDATE-ONLY MENTOR
# ============================================================
def mentor_candidate(candidate_slug: str, question: str, memory=None):
    candidate = get_object_or_404(CandidateProfile, slug=candidate_slug)
    memory = memory or []

    prompt = f"""
You are LYRA, a friendly career mentor.

Candidate Resume:
{candidate.resume_data}
"""

    messages = [{"role": "system", "content": prompt}, *memory, {"role": "user", "content": question}]
    reply = client.chat.completions.create(model="gpt-5", messages=messages).choices[0].message.content

    return {
        "reply": reply,
        "memory": memory + [{"role": "user", "content": question}, {"role": "assistant", "content": reply}],
    }


from main.chat_store import (
    get_or_create_session,
    load_history,
    save_message,
)


def lyra_chat_supabase(
    message: str,
    *,
    session_id=None,
    mode="candidate",
    user_id=None,
    candidate_slug=None,
):
    """
    Conversational LYRA using Supabase-backed memory.
    """

    # 1️⃣ Session
    session = get_or_create_session(
        session_id=session_id,
        mode=mode,
        user_id=user_id,
        candidate_slug=candidate_slug,
    )

    # 2️⃣ History
    history = load_history(session)

    system_prompt = """
        You are LYRA — a friendly, warm, supportive AI career mentor.
        Be conversational and natural.
        Ask short follow-up questions when useful.
        Never invent facts; rely only on provided context.
    """

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})
    
    FAST_MODEL = "gpt-5-mini"
    DEEP_MODEL = "gpt-5"
    
    deep_keywords = (
        "roadmap",
        "plan",
        "architecture",
        "design",
        "compare",
        "strategy",
        "6 month",
        "12 month",
    )
    
    use_deep = any(k in message.lower() for k in deep_keywords)
    
    resp = client.chat.completions.create(
        model=DEEP_MODEL if use_deep else FAST_MODEL,
        messages=messages,
    )

    # # 3️⃣ GPT-5 call
    # resp = client.chat.completions.create(
    #     model="gpt-5",
    #     messages=messages,
    # )

    reply = resp.choices[0].message.content

    # 4️⃣ Persist
    save_message(session, "user", message)
    save_message(session, "assistant", reply)

    return {
        "reply": reply,
        "session_id": str(session.id),
    }
