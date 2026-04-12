"""
Phase 0.6: papers_db + users_db JSON 持久化层

- papers_db: /root/.openclaw/rag-data/papers_db.json
- users_db:  /root/.openclaw/rag-data/users_db.json
  (users_by_email 从 users_db 推导，无需独立存储)

启动时从 JSON 恢复，运行时每次写入自动落盘（原子替换）。
"""
import json, os, threading
from pathlib import Path
from typing import Any

DATA_DIR = Path("/root/.openclaw/rag-data")
PAPERS_DB_FILE = DATA_DIR / "papers_db.json"
USERS_DB_FILE  = DATA_DIR / "users_db.json"

_lock = threading.Lock()
_users_db: dict = {}  # 全局 users_db 实例

# ── papers_db ─────────────────────────────────────────
# 结构: { paper_id: { paper_id, user_id, title, status, chunks_count, collection, error, created_at } }
_papers_db: dict[str, dict] = {}

def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"⚠️ 加载 {path.name} 失败: {e}")
    return {}

def _save_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(path))  # 原子替换
    except Exception as e:
        print(f"⚠️ 保存 {path.name} 失败: {e}")

def init_papers() -> None:
    global _papers_db
    _papers_db = _load_json(PAPERS_DB_FILE)
    print(f"📂 papers_db 加载: {len(_papers_db)} 条")

def init_users() -> tuple[dict, dict]:
    """返回 (users_db, users_by_email)"""
    global _users_db
    _users_db = _load_json(USERS_DB_FILE)
    by_email = {u["email"]: u for u in _users_db.values()}
    print(f"📂 users_db 加载: {len(_users_db)} 用户")
    return _users_db, by_email

# papers_db 操作
def save_users() -> None:
    _save_json(USERS_DB_FILE, _users_db)

def get_papers_db() -> dict:
    return _papers_db

def get_paper(paper_id: str) -> dict | None:
    return _papers_db.get(paper_id)

def upsert_paper(paper_id: str, data: dict) -> None:
    with _lock:
        _papers_db[paper_id] = data
        _save_json(PAPERS_DB_FILE, _papers_db)

def update_paper(paper_id: str, **kwargs) -> None:
    with _lock:
        if paper_id in _papers_db:
            _papers_db[paper_id].update(kwargs)
            _save_json(PAPERS_DB_FILE, _papers_db)

def delete_paper(paper_id: str) -> None:
    with _lock:
        _papers_db.pop(paper_id, None)
        _save_json(PAPERS_DB_FILE, _papers_db)

def get_user_papers(user_id: str) -> list[str]:
    """返回属于指定用户的论文 ID 列表"""
    return [
        pid for pid, p in _papers_db.items()
        if p.get("user_id") == user_id
    ]

# ── users_db ─────────────────────────────────────────
def _save_users(db: dict) -> None:
    _save_json(USERS_DB_FILE, db)
