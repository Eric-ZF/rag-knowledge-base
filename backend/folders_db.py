"""
Phase 0.8: folders_db — 文件夹数据库（JSON 文件持久化）

数据结构：folders_db[folder_id] = {
    "folder_id": str,
    "user_id": str,
    "name": str,
    "parent_id": str | None,
    "created_at": str (ISO),
}
"""
import json, os, threading
from pathlib import Path
from typing import Any

import logging
logger = logging.getLogger(__name__)

DATA_DIR    = Path("/root/.openclaw/rag-data")
FOLDERS_FILE = DATA_DIR / "folders_db.json"

_lock = threading.Lock()
_folders_db: dict[str, dict] = {}

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

def init() -> None:
    global _folders_db
    _folders_db = _load(FOLDERS_FILE)
    logger.info(f"folders_db 加载: {len(_folders_db)} 个文件夹")

def get_all() -> dict[str, dict]:
    return _folders_db

def get(folder_id: str) -> dict | None:
    return _folders_db.get(folder_id)

def get_user_folders(user_id: str) -> list[dict]:
    """返回属于用户的顶层文件夹（parent_id=None）"""
    return [f for f in _folders_db.values() if f["user_id"] == user_id and f["parent_id"] is None]

def get_child_folders(parent_id: str) -> list[dict]:
    """返回子文件夹"""
    return [f for f in _folders_db.values() if f["parent_id"] == parent_id]

def create(folder_id: str, user_id: str, name: str, parent_id: str | None = None) -> dict:
    from datetime import datetime
    with _lock:
        folder = {
            "folder_id": folder_id,
            "user_id": user_id,
            "name": name,
            "parent_id": parent_id,
            "created_at": datetime.utcnow().isoformat(),
        }
        _folders_db[folder_id] = folder
        _save(FOLDERS_FILE, _folders_db)
        return folder

def rename(folder_id: str, name: str) -> None:
    with _lock:
        if folder_id in _folders_db:
            _folders_db[folder_id]["name"] = name
            _save(FOLDERS_FILE, _folders_db)

def move(folder_id: str, new_parent_id: str | None) -> None:
    with _lock:
        if folder_id in _folders_db:
            _folders_db[folder_id]["parent_id"] = new_parent_id
            _save(FOLDERS_FILE, _folders_db)

def delete(folder_id: str) -> None:
    """删除文件夹（不删除内部论文，论文的 folder_id 需由调用方处理）"""
    with _lock:
        # 同时删除所有子文件夹
        to_delete = {folder_id}
        children = get_child_folders(folder_id)
        while children:
            for c in children:
                to_delete.add(c["folder_id"])
            grandchildren = []
            for cid in to_delete:
                grandchildren.extend(get_child_folders(cid))
            children = grandchildren
        for did in to_delete:
            _folders_db.pop(did, None)
        _save(FOLDERS_FILE, _folders_db)

def count_user_folders(user_id: str) -> int:
    return len([f for f in _folders_db.values() if f["user_id"] == user_id])
