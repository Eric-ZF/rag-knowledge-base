"""
Phase 0.8: papers_db + users_db JSON 持久化层

- papers_db: /root/.openclaw/rag-data/papers_db.json
  结构: { paper_id: { paper_id, user_id, folder_id, title, status, chunks_count, ... } }
- users_db:  /root/.openclaw/rag-data/users_db.json
  结构: { user_id: { user_id, phone, email, password, plan, created_at } }
- folders_db: /root/.openclaw/rag-data/folders_db.json  (见 folders_db.py)
"""
import json, os, threading
from pathlib import Path
from datetime import datetime

import logging
logger = logging.getLogger(__name__)
from typing import Any

DATA_DIR = Path("/root/.openclaw/rag-data")
PAPERS_DB_FILE = DATA_DIR / "papers_db.json"
USERS_DB_FILE  = DATA_DIR / "users_db.json"

_lock = threading.Lock()
_users_db: dict = {}

# ── 通用读写 ─────────────────────────────────────────
def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"加载 {path.name} 失败: {e}")
    return {}

def _save(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(path))
    except Exception as e:
        logger.warning(f"保存 {path.name} 失败: {e}")

# ── papers_db ─────────────────────────────────────────
_papers_db: dict[str, dict] = {}

def init_papers() -> None:
    global _papers_db
    _papers_db = _load(PAPERS_DB_FILE)
    # 确保 folder_id 字段存在（向后兼容旧数据）
    for p in _papers_db.values():
        p.setdefault("folder_id", None)
    logger.info(f"papers_db 加载: {len(_papers_db)} 条")

def init_users() -> tuple[dict, dict]:
    global _users_db
    _users_db = _load(USERS_DB_FILE)
    # 确保 phone 字段存在（向后兼容旧数据）
    for u in _users_db.values():
        u.setdefault("phone", "")
        u.setdefault("created_at", "")
    by_email = {u.get("email", ""): u for u in _users_db.values() if u.get("email")}
    by_phone  = {u.get("phone", ""): u for u in _users_db.values() if u.get("phone")}
    logger.info(f"users_db 加载: {len(_users_db)} 用户")
    return _users_db, by_email, by_phone

def save_users() -> None:
    _save(USERS_DB_FILE, _users_db)

def get_papers_db() -> dict:
    """返回全量论文（读穿透）"""
    return _load(PAPERS_DB_FILE)

def get_paper(paper_id: str) -> dict | None:
    """按 ID 读取论文（读穿透）"""
    return _load(PAPERS_DB_FILE).get(paper_id)

def upsert_paper(paper_id: str, data: dict) -> None:
    with _lock:
        _papers_db[paper_id] = data
        _save(PAPERS_DB_FILE, _papers_db)

def update_paper(paper_id: str, **kwargs) -> None:
    with _lock:
        if paper_id in _papers_db:
            _papers_db[paper_id].update(kwargs)
            _save(PAPERS_DB_FILE, _papers_db)

def delete_paper(paper_id: str) -> None:
    with _lock:
        _papers_db.pop(paper_id, None)
        _save(PAPERS_DB_FILE, _papers_db)

def get_user_papers(user_id: str) -> list[dict]:
    """返回属于指定用户的论文。
    
    读穿透策略：每次直接从磁盘加载，确保 rebuild 等外部进程
    写入后能立即反映最新状态，对用户完全透明。
    """
    return [p for p in _load(PAPERS_DB_FILE).values() if p.get("user_id") == user_id]

def get_folder_papers(folder_id: str) -> list[dict]:
    """返回属于指定文件夹的论文（读穿透）"""
    return [p for p in _load(PAPERS_DB_FILE).values() if p.get("folder_id") == folder_id]

def move_papers_to_folder(paper_ids: list[str], target_folder_id: str) -> None:
    """批量移动论文到目标文件夹"""
    with _lock:
        data = _load(PAPERS_DB_FILE)
        for pid in paper_ids:
            if pid in data:
                data[pid]["folder_id"] = target_folder_id
        _save(PAPERS_DB_FILE, data)

def assign_default_folder(user_id: str, folder_id: str) -> None:
    """为用户设置默认文件夹"""
    with _lock:
        if user_id in _users_db:
            _users_db[user_id]["default_folder_id"] = folder_id
            _save(USERS_DB_FILE, _users_db)
