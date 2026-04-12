"""
共享状态 — papers_db / users_db 全局单例
避免循环导入：routers 和 main.py 都从这里 import
"""
import threading
from typing import TypedDict

# ─── SSE 索引进度 ────────────────────────────────────
processing_events: dict[str, dict] = {}
_pe_lock = threading.Lock()

# ─── users DB ─────────────────────────────────────────
users_db: dict = {}
users_by_email: dict = {}

def get_users_db():
    return users_db

def get_users_by_email():
    return users_by_email

def set_users(db: dict, by_email: dict):
    global users_db, users_by_email
    users_db = db
    users_by_email = by_email
