#!/usr/bin/env python3
"""
Phase 1: 重建 ChromaDB 索引（强制 BGE 1024d）

问题：ChromaDB 里存的是 384d 向量（text2vec），pipeline 用 BGE 1024d 查询失败。

解决：
1. 从 ChromaDB 提取所有文档
2. 手动用 BGE 生成 1024d 向量
3. 删除旧 collection，创建新的（指定 1024d），显式 add_embeddings
4. 验证查询正常
"""
import sys, os, re
sys.path.insert(0, '/root/.openclaw/workspace/rag-knowledge-base/phase0/backend')
os.chdir('/root/.openclaw/workspace/rag-knowledge-base/phase0/backend')

from config import CHROMADB_DIR
import chromadb

COLLECTION_NAME = "user_1d2a4dc3_550f_4f89_b97b_2b057705381c"
safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", COLLECTION_NAME)

# ── 1. 提取文档 ─────────────────────────────────
client = chromadb.PersistentClient(path=CHROMADB_DIR)

print(f"📂 正在加载 collection: {COLLECTION_NAME}")
try:
    old_col = client.get_collection(COLLECTION_NAME)
except Exception as e:
    print(f"❌ 无法访问: {e}")
    sys.exit(1)

all_r = old_col.get(include=["documents", "metadatas"])
docs_raw = all_r.get("documents", [])
metas_raw = all_r.get("metadatas", [])
print(f"   原始 chunks: {len(docs_raw)}")

# 去重（paper_id + chunk_index 唯一）
seen = set()
unique_docs, unique_metas = [], []
for doc, meta in zip(docs_raw, metas_raw):
    key = (meta.get("paper_id"), meta.get("chunk_index"))
    if key not in seen:
        seen.add(key)
        unique_docs.append(doc)
        unique_metas.append(meta)
print(f"   去重后: {len(unique_docs)} chunks")

# 按 paper 分组
papers: dict[str, list] = {}
for doc, meta in zip(unique_docs, unique_metas):
    pid = meta.get("paper_id", "unknown")
    papers.setdefault(pid, []).append((doc, meta))

print(f"\n📄 论文:")
for pid, chunks in papers.items():
    title = chunks[0][1].get("title") or chunks[0][0][:40]
    print(f"  {pid[:8]}: {len(chunks)} chunks | {title[:50]}")

# ── 2. 删除旧 collection ──────────────────────────
print(f"\n🗑️ 删除旧 collection...")
try:
    client.delete_collection(name=COLLECTION_NAME)
    print(f"   ✅ 已删除 '{COLLECTION_NAME}'")
except Exception as e:
    print(f"   ⚠️ {e}")

# ── 3. 获取 BGE embedding 函数 ───────────────────
from pipeline import get_chroma_embedding_fn
embedding_fn = get_chroma_embedding_fn()
print(f"\n📊 生成 {len(unique_docs)} 个 BGE 1024d 向量...")
all_embeddings = embedding_fn.embed_documents(unique_docs)
print(f"   ✅ embeddings: ({len(all_embeddings)}, dim={len(all_embeddings[0])})")

# ── 4. 创建新 collection ─────────────────────────
print(f"\n🏗️ 创建新 collection: {safe_name}（embedding_dimension=1024）")
new_col = client.create_collection(
    name=safe_name,
    metadata={"embedding_dimension": 1024, "model": "BAAI/bge-large-zh-v1.5"},
)
print(f"   ✅ 创建成功")

# ── 5. 添加文档（显式 embeddings）──────────────────
ids = [f"chunk_{i}" for i in range(len(unique_docs))]
new_col.add(
    ids=ids,
    documents=unique_docs,
    embeddings=all_embeddings,
    metadatas=unique_metas,
)
print(f"   ✅ 添加 {len(unique_docs)} 文档 + embeddings")

# ── 6. 验证 ────────────────────────────────────
count = new_col.count()
print(f"\n✅ collection '{COLLECTION_NAME}' 现在有 {count} chunks")

print("\n🔍 验证向量检索...")
results = new_col.query(
    query_texts=["欧盟碳边境调节机制 扩散 影响"],
    n_results=2,
    include=["documents", "metadatas"],
)
docs = results.get("documents", [[]])
print(f"   ✅ 查询成功! 返回 {len(docs[0])} 条")
for d in docs[0][:2]:
    print(f"      - {d[:60]}...")

# ── 7. 更新 papers_db.json ─────────────────────
print("\n📝 同步更新 papers_db.json...")
from data import upsert_paper
for pid, chunks in papers.items():
    title = chunks[0][1].get("title") or chunks[0][0][:30]
    upsert_paper(pid, {
        "paper_id": pid,
        "user_id": "old-bosstest",
        "title": title,
        "status": "ready",
        "chunks_count": len(chunks),
        "collection": COLLECTION_NAME,
    })
    print(f"   ✅ {pid[:8]}: {title[:40]} → chunks={len(chunks)}")

print("\n🎉 ChromaDB 重建完成，全部使用 BGE 1024d 向量！")
