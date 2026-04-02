"""
Phase 1 — 数据库 Schema
SQLite（关系数据）+ ChromaDB（向量数据）
"""
import sqlite3, uuid
from pathlib import Path
from typing import Generator
from contextlib import contextmanager
from . import config

# ─── Schema SQL ───────────────────────────────────────
SCHEMA_SQL = """
-- 文献主表
CREATE TABLE IF NOT EXISTS papers (
    paper_id      TEXT PRIMARY KEY,  -- UUID
    title         TEXT NOT NULL,
    authors       TEXT,             -- JSON 数组
    year          INTEGER,
    source        TEXT,             -- 期刊/会议/预印本
    journal       TEXT,
    doi           TEXT,
    language      TEXT DEFAULT 'en',  -- zh / en
    abstract      TEXT,
    keywords      TEXT,             -- JSON 数组
    version       TEXT DEFAULT 'published',  -- preprint / accepted / published
    file_hash     TEXT UNIQUE,      -- SHA256，用于去重
    file_path     TEXT,             -- 原始文件路径
    file_name     TEXT,             -- 原始文件名
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

-- 章节表
CREATE TABLE IF NOT EXISTS sections (
    section_id    TEXT PRIMARY KEY,
    paper_id      TEXT NOT NULL,
    title         TEXT,
    path          TEXT,             -- 如 "1.2.3"
    section_order INTEGER,
    page_start    INTEGER,
    page_end      INTEGER,
    text          TEXT,
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
);

-- 证据块表（Recall Chunks + Evidence Chunks 两级）
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id          TEXT PRIMARY KEY,
    paper_id          TEXT NOT NULL,
    section_id       TEXT,
    chunk_type        TEXT DEFAULT 'body',  -- body / table / figure / abstract / conclusion / method
    chunk_level       TEXT DEFAULT 'recall',  -- recall / evidence
    recall_chunk_id   TEXT,             -- 所属的 recall chunk（evidence 级有）
    chunk_text        TEXT NOT NULL,
    token_count       INTEGER,
    page_range        TEXT,             -- 如 "3-5"
    keywords_extracted TEXT,            -- JSON 数组
    chroma_id         TEXT,             -- ChromaDB 中的 ID
    created_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES sections(section_id) ON DELETE SET NULL,
    FOREIGN KEY (recall_chunk_id) REFERENCES chunks(chunk_id) ON DELETE SET NULL
);

-- 文献画像表（学术语义抽取结果）
CREATE TABLE IF NOT EXISTS paper_profiles (
    paper_id          TEXT PRIMARY KEY,
    research_question TEXT,
    research_object   TEXT,
    data_source       TEXT,
    time_span         TEXT,
    methods           TEXT,             -- JSON 数组
    mechanisms        TEXT,             -- JSON 数组
    main_findings     TEXT,
    heterogeneity     TEXT,
    policy_implication TEXT,
    limitations       TEXT,
    profile_text      TEXT,             -- 完整画像文本（供检索用）
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
);

-- 问答日志表
CREATE TABLE IF NOT EXISTS qa_logs (
    query_id              TEXT PRIMARY KEY,
    user_query            TEXT NOT NULL,
    rewritten_query       TEXT,
    mode                  TEXT DEFAULT 'default',  -- default / survey / compare
    retrieved_chunk_ids   TEXT,   -- JSON 数组
    selected_chunk_ids    TEXT,   -- JSON 数组
    answer_text           TEXT,
    citation_list         TEXT,   -- JSON 数组 [{chunk_id, paper_id, ...}]
    feedback_score        INTEGER, -- 1=bad, 2=ok, 3=good, 4=great, 5=excellent
    feedback_reason       TEXT,
    latency_ms            INTEGER,
    created_at            TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE SET NULL
);

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    user_id    TEXT PRIMARY KEY,
    email      TEXT UNIQUE NOT NULL,
    password   TEXT NOT NULL,   -- bcrypt hash
    plan       TEXT DEFAULT 'free',
    created_at TEXT DEFAULT (datetime('now'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_chunks_paper_id ON chunks(paper_id);
CREATE INDEX IF NOT EXISTS idx_chunks_type ON chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_chunks_level ON chunks(chunk_level);
CREATE INDEX IF NOT EXISTS idx_sections_paper_id ON sections(paper_id);
CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
CREATE INDEX IF NOT EXISTS idx_papers_language ON papers(language);
CREATE INDEX IF NOT EXISTS idx_papers_file_hash ON papers(file_hash);
CREATE INDEX IF NOT EXISTS idx_qa_logs_created ON qa_logs(created_at);
"""


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """SQLite 上下文管理器（线程安全）"""
    Path(config.SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(config.SQLITE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据库（建表）"""
    Path(config.SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
    print(f"✅ 数据库初始化完成: {config.SQLITE_PATH}")
