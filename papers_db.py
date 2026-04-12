"""
papers_db — 论文数据库（JSON 文件持久化）

任何对 papers_db 的写入都会自动同步到磁盘。
每次写入后调用 save()，确保 backend 重启/崩溃不丢失数据。

数据结构：papers_db[paper_id] = {
    "paper_id": str,
    "user_id": str,
    "title": str,
    "status": "processing" | "ready" | "error",
    "chunks_count": int | None,
    "collection": str,
    "error": str | None,
    "created_at": str (ISO),
}
"""
import json
import os
import threading
import atexit
from pathlib import Path
from typing import Any

_papers_db: dict[str, dict] = {}
_lock = threading.Lock()
_persistence_path: str | None = None


def init(persistence_path: str) -> None:
    """从 JSON 文件加载 papers_db（backend 启动时调用）"""
    global _papers_db, _persistence_path
    _persistence_path = persistence_path

    if os.path.exists(persistence_path):
        try:
            with open(persistence_path, "r", encoding="utf-8") as f:
                _papers_db = json.load(f)
            print(f"📂 papers_db 从 {persistence_path} 加载，{len(_papers_db)} 条记录")
        except Exception as e:
            print(f"⚠️ papers_db 加载失败（将重新创建）: {e}")
            _papers_db = {}
    else:
        _papers_db = {}
        print(f"📂 papers_db 新建（文件不存在）")


def save() -> None:
    """将 papers_db 同步写入磁盘（每次写入后自动调用）"""
    if not _persistence_path:
        return
    tmp = _persistence_path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_papers_db, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _persistence_path)  # 原子替换
    except Exception as e:
        print(f"⚠️ papers_db 保存失败: {e}")

atexit.register(save)  # 优雅退出时强制刷盘


def get_all() -> dict[str, dict]:
    return _papers_db


def get(paper_id: str) -> dict | None:
    return _papers_db.get(paper_id)


def upsert(paper_id: str, data: dict[str, Any]) -> None:
    """插入或更新一条记录，并持久化"""
    with _lock:
        _papers_db[paper_id] = data
        save()


def update_status(paper_id: str, status: str, **kwargs) -> None:
    """更新论文状态（processing→ready/error），并持久化"""
    with _lock:
        if paper_id in _papers_db:
            _papers_db[paper_id]["status"] = status
            for k, v in kwargs.items():
                _papers_db[paper_id][k] = v
            save()


def delete(paper_id: str) -> bool:
    """删除一条记录，并持久化"""
    with _lock:
        if paper_id in _papers_db:
            del _papers_db[paper_id]
            save()
            return True
        return False


def clear() -> None:
    """清空所有记录（谨慎使用），并持久化"""
    with _lock:
        _papers_db.clear()
        save()
