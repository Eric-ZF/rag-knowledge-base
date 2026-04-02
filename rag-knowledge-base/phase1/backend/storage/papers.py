"""
Phase 1 — 文献 CRUD
"""
import json, uuid, hashlib, sqlite3
from pathlib import Path
from typing import Optional
from .schema import get_db
from .. import config


def generate_uuid() -> str:
    return str(uuid.uuid4())


def compute_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


# ─── Papers ────────────────────────────────────────────

def create_paper(
    title: str,
    file_bytes: bytes,
    file_name: str,
    authors: list[str] | None = None,
    year: int | None = None,
    source: str = "",
    journal: str = "",
    doi: str = "",
    language: str = "en",
    abstract: str = "",
    keywords: list[str] | None = None,
    version: str = "published",
) -> dict:
    """创建文献记录（含文件存储）"""
    paper_id = generate_uuid()
    file_hash = compute_file_hash(file_bytes)

    # 检查是否重复上传
    with get_db() as conn:
        existing = conn.execute(
            "SELECT paper_id, title FROM papers WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        if existing:
            raise ValueError(f"该文件已上传，paper_id: {existing['paper_id']}, 标题: {existing['title']}")

    # 保存原始文件
    file_dir = config.FILES_DIR / paper_id[0:2]
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / f"{paper_id}.pdf"
    file_path.write_bytes(file_bytes)

    with get_db() as conn:
        conn.execute(
            """INSERT INTO papers
               (paper_id, title, authors, year, source, journal, doi, language,
                abstract, keywords, version, file_hash, file_path, file_name)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                paper_id, title,
                json.dumps(authors or [], ensure_ascii=False),
                year, source, journal, doi, language,
                abstract,
                json.dumps(keywords or [], ensure_ascii=False),
                version,
                file_hash, str(file_path), file_name,
            ),
        )

    return get_paper(paper_id)


def get_paper(paper_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
        if not row:
            return None
        return dict(row)


def get_all_papers(user_id: str | None = None, limit: int = 100) -> list[dict]:
    """获取所有文献列表"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT paper_id, title, authors, year, source, journal, language, "
            "version, created_at FROM papers "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def update_paper(paper_id: str, **fields) -> dict | None:
    allowed = {"title", "authors", "year", "source", "journal", "doi",
               "language", "abstract", "keywords", "version"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return get_paper(paper_id)
    if "authors" in fields and isinstance(fields["authors"], list):
        fields["authors"] = json.dumps(fields["authors"], ensure_ascii=False)
    if "keywords" in fields and isinstance(fields["keywords"], list):
        fields["keywords"] = json.dumps(fields["keywords"], ensure_ascii=False)
    fields["updated_at"] = "datetime('now')"
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [paper_id]
    with get_db() as conn:
        conn.execute(f"UPDATE papers SET {sets} WHERE paper_id = ?", vals)
    return get_paper(paper_id)


def delete_paper(paper_id: str) -> bool:
    with get_db() as conn:
        # 删除文件
        row = conn.execute("SELECT file_path FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
        if row and row["file_path"]:
            Path(row["file_path"]).unlink(missing_ok=True)
        conn.execute("DELETE FROM papers WHERE paper_id = ?", (paper_id,))
        return True


def check_duplicate_hash(file_hash: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT paper_id, title, version FROM papers WHERE file_hash = ?",
            (file_hash,),
        ).fetchone()
        return dict(row) if row else None


# ─── Sections ──────────────────────────────────────────

def create_section(
    paper_id: str,
    title: str = "",
    path: str = "",
    section_order: int = 0,
    page_start: int | None = None,
    page_end: int | None = None,
    text: str = "",
) -> str:
    section_id = generate_uuid()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO sections
               (section_id, paper_id, title, path, section_order, page_start, page_end, text)
               VALUES (?,?,?,?,?,?,?,?)""",
            (section_id, paper_id, title, path, section_order, page_start, page_end, text),
        )
    return section_id


def get_sections_by_paper(paper_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM sections WHERE paper_id = ? ORDER BY section_order",
            (paper_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Chunks ────────────────────────────────────────────

def create_chunk(
    paper_id: str,
    chunk_text: str,
    chunk_level: str = "recall",  # recall / evidence
    chunk_type: str = "body",
    section_id: str | None = None,
    recall_chunk_id: str | None = None,
    token_count: int = 0,
    page_range: str = "",
    keywords_extracted: list[str] | None = None,
    chroma_id: str = "",
) -> str:
    chunk_id = generate_uuid()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO chunks
               (chunk_id, paper_id, section_id, chunk_level, chunk_type,
                recall_chunk_id, chunk_text, token_count, page_range,
                keywords_extracted, chroma_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                chunk_id, paper_id, section_id, chunk_level, chunk_type,
                recall_chunk_id, chunk_text, token_count, page_range,
                json.dumps(keywords_extracted or [], ensure_ascii=False),
                chroma_id,
            ),
        )
    return chunk_id


def get_chunks_by_paper(paper_id: str, chunk_level: str | None = None) -> list[dict]:
    with get_db() as conn:
        if chunk_level:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE paper_id = ? AND chunk_level = ? ORDER BY chunk_id",
                (paper_id, chunk_level),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM chunks WHERE paper_id = ? ORDER BY chunk_id",
                (paper_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_chunk_by_id(chunk_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
        return dict(row) if row else None


def get_chunks_by_ids(chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    placeholders = ",".join("?" * len(chunk_ids))
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT c.*, p.title as paper_title, p.authors as paper_authors "
            f"FROM chunks c JOIN papers p ON c.paper_id = p.paper_id "
            f"WHERE c.chunk_id IN ({placeholders})",
            chunk_ids,
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Paper Profiles ────────────────────────────────────

def upsert_profile(
    paper_id: str,
    research_question: str = "",
    research_object: str = "",
    data_source: str = "",
    time_span: str = "",
    methods: list[str] | None = None,
    mechanisms: list[str] | None = None,
    main_findings: str = "",
    heterogeneity: str = "",
    policy_implication: str = "",
    limitations: str = "",
    profile_text: str = "",
) -> dict:
    with get_db() as conn:
        conn.execute(
            """INSERT INTO paper_profiles
               (paper_id, research_question, research_object, data_source, time_span,
                methods, mechanisms, main_findings, heterogeneity,
                policy_implication, limitations, profile_text, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?, datetime('now'))
               ON CONFLICT(paper_id) DO UPDATE SET
                research_question=excluded.research_question,
                research_object=excluded.research_object,
                data_source=excluded.data_source,
                time_span=excluded.time_span,
                methods=excluded.methods,
                mechanisms=excluded.mechanisms,
                main_findings=excluded.main_findings,
                heterogeneity=excluded.heterogeneity,
                policy_implication=excluded.policy_implication,
                limitations=excluded.limitations,
                profile_text=excluded.profile_text,
                updated_at=datetime('now')""",
            (
                paper_id, research_question, research_object, data_source, time_span,
                json.dumps(methods or [], ensure_ascii=False),
                json.dumps(mechanisms or [], ensure_ascii=False),
                main_findings, heterogeneity, policy_implication, limitations, profile_text,
            ),
        )
    with get_db() as conn:
        return dict(conn.execute(
            "SELECT * FROM paper_profiles WHERE paper_id = ?", (paper_id,)
        ).fetchone())


def get_profile(paper_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM paper_profiles WHERE paper_id = ?", (paper_id,)
        ).fetchone()
        return dict(row) if row else None


# ─── QA Logs ───────────────────────────────────────────

def create_qa_log(
    user_query: str,
    rewritten_query: str = "",
    mode: str = "default",
    retrieved_chunk_ids: list[str] | None = None,
    selected_chunk_ids: list[str] | None = None,
    answer_text: str = "",
    citation_list: list[dict] | None = None,
    latency_ms: int = 0,
) -> str:
    query_id = generate_uuid()
    with get_db() as conn:
        conn.execute(
            """INSERT INTO qa_logs
               (query_id, user_query, rewritten_query, mode,
                retrieved_chunk_ids, selected_chunk_ids,
                answer_text, citation_list, latency_ms)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                query_id, user_query, rewritten_query, mode,
                json.dumps(retrieved_chunk_ids or [], ensure_ascii=False),
                json.dumps(selected_chunk_ids or [], ensure_ascii=False),
                answer_text, json.dumps(citation_list or [], ensure_ascii=False),
                latency_ms,
            ),
        )
    return query_id


def update_qa_feedback(query_id: str, score: int, reason: str = "") -> bool:
    with get_db() as conn:
        conn.execute(
            "UPDATE qa_logs SET feedback_score = ?, feedback_reason = ? WHERE query_id = ?",
            (score, reason, query_id),
        )
        return True


def get_recent_qa_logs(limit: int = 50) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT query_id, user_query, answer_text, feedback_score, created_at "
            "FROM qa_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
