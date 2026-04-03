#!/usr/bin/env python3
"""
rebuild_papers.py — 论文池重建脚本

用途：
1. 清理 ChromaDB（重建 collection，确保 embedding 维度一致）
2. 重置 papers_db
3. 输出需要重新上传的 PDF 列表

用法：
  python3 rebuild_papers.py [--keep-existing]
  
注意：必须先让用户重新上传 PDF，才能真正重建索引。
本脚本只做清理和诊断。
"""
import argparse
import chromadb
import json
import os
import shutil

CHROMADB_DIR = '/tmp/chromadb'
PAPERS_DB_PATH = '/root/.openclaw/rag-data/papers_db.json'
COLLECTION_NAME = 'user_1d2a4dc3_550f_4f89_b97b_2b057705381c'

def load_papers_db():
    if os.path.exists(PAPERS_DB_PATH):
        with open(PAPERS_DB_PATH) as f:
            return json.load(f)
    return {}

def diagnose(chroma_client):
    """诊断当前 ChromaDB 状态"""
    print("=" * 60)
    print("🔍 ChromaDB 诊断")
    print("=" * 60)
    
    try:
        col = chroma_client.get_collection(COLLECTION_NAME)
        total = col.count()
        print(f"Collection: {COLLECTION_NAME}")
        print(f"Total chunks: {total}")
        
        # Get sample to check metadata
        if total > 0:
            sample = col.peek(limit=min(5, total), include=['metadatas'])
            for i, meta in enumerate(sample.get('metadatas', [])):
                pid = meta.get('paper_id', '???')
                title = meta.get('title', '???')
                print(f"  Chunk {i}: paper_id={pid[:8]}, title={repr(title)[:40]}")
    except Exception as e:
        print(f"Collection error: {e}")

def reset_chromadb(chroma_client):
    """删除旧 collection，重新创建（统一 embedding 维度）"""
    print("\n🗑️  重置 ChromaDB collection...")
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
        print(f"  Deleted collection: {COLLECTION_NAME}")
    except Exception as e:
        print(f"  Delete error (may not exist): {e}")
    
    # 重建 collection（使用当前 pipeline.py 中的 embedding 维度）
    # 注意：新索引需要先上传 PDF 才能填充
    from backend.config import EMBEDDING_DIM
    new_col = chroma_client.create_collection(
        name=COLLECTION_NAME,
        get_or_create=True,
        metadata={"embedding_dim": EMBEDDING_DIM}
    )
    print(f"  Created fresh collection (dimension: {EMBEDDING_DIM})")
    return new_col

def reset_papers_db():
    """重置 papers_db 为空（或者只保留状态）"""
    print("\n📄 重置 papers_db...")
    backup = PAPERS_DB_PATH + '.backup.' + str(int(os.path.getmtime(PAPERS_DB_PATH)))
    shutil.copy(PAPERS_DB_PATH, backup)
    print(f"  Backed up to: {backup}")
    
    # 重置为只有用户信息，无论文
    papers_db = load_papers_db()
    for pid in list(papers_db.keys()):
        papers_db[pid]['status'] = 'pending_reupload'
        papers_db[pid]['chunks_count'] = None
        papers_db[pid]['error'] = '需要重新上传 PDF 重建索引'
    
    with open(PAPERS_DB_PATH, 'w') as f:
        json.dump(papers_db, f, ensure_ascii=False, indent=2)
    print(f"  Reset papers_db (marked all as pending_reupload)")

def main():
    parser = argparse.ArgumentParser(description='重建论文池')
    parser.add_argument('--keep-chromadb', action='store_true', help='保留现有 ChromaDB 数据（只诊断）')
    args = parser.parse_args()

    chroma_client = chromadb.PersistentClient(path=CHROMADB_DIR)
    
    # 诊断
    diagnose(chroma_client)
    
    if args.keep_chromadb:
        print("\n✅ 诊断完成（未做任何修改）")
        return
    
    # 重建
    print("\n" + "=" * 60)
    print("⚠️  即将重置 ChromaDB 和 papers_db！")
    print("=" * 60)
    confirm = input("输入 'yes' 确认重建：")
    if confirm != 'yes':
        print("取消。")
        return
    
    reset_chromadb(chroma_client)
    reset_papers_db()
    
    print("\n✅ 重建完成！")
    print("\n📋 下一步：")
    print("  1. 重新上传以下论文的 PDF：")
    papers = load_papers_db()
    for pid, info in papers.items():
        print(f"     - {info['title']} (原 paper_id: {pid[:8]})")
    print("  2. 上传后系统将自动重建索引")
    print("  3. 索引完成后论文池管理界面将恢复正常")

if __name__ == '__main__':
    main()
