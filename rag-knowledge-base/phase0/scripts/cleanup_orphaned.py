#!/usr/bin/env python3
"""
Phase 0.6 — 清理废弃的 ChromaDB collections
只保留 users_db.json 中实际存在的用户的 collection
"""
import sys, json
sys.path.insert(0, '/root/.openclaw/workspace/rag-knowledge-base/phase0/backend')

import chromadb
from pathlib import Path

DATA_DIR = Path("/root/.openclaw/rag-data")
CHROMADB_DIR = DATA_DIR / "chromadb"
USERS_DB_FILE = DATA_DIR / "users_db.json"

# 加载 users_db.json 中所有有效的 collection 名
users_db = json.loads(USERS_DB_FILE.read_text())
valid_collections = {u["collection"] for u in users_db.values()}
print(f"✅ 有效 collections: {valid_collections}")

# 扫描 ChromaDB
client = chromadb.PersistentClient(path=str(CHROMADB_DIR))
all_collections = {col.name for col in client.list_collections()}
print(f"📂 ChromaDB 总 collections: {all_collections}")

# 找出废弃的
orphaned = all_collections - valid_collections
if not orphaned:
    print("✅ 没有废弃 collection，无需清理")
else:
    print(f"🗑️ 发现 {len(orphaned)} 个废弃 collection:")
    for name in orphaned:
        try:
            col = client.get_collection(name)
            count = col.count()
            col.delete()
            print(f"   已删除: {name} ({count} chunks)")
        except Exception as e:
            print(f"   ❌ 删除失败 {name}: {e}")

# 清理后验证
remaining = {col.name for col in client.list_collections()}
print(f"\n📂 清理后剩余 collections: {remaining}")
print("✅ 清理完成")
