#!/usr/bin/env python3
"""
重建所有论文的 ChromaDB 索引
"""
import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from config import CHROMADB_DIR, PAPERS_DIR
from pipeline import process_pdf
from papers_db import get_all as get_papers_db, update_status, save as save_papers

PAPERS_DB_PATH = "/root/.openclaw/rag-data/papers_db.json"
PROCESSING_EVENTS = {}
_PE_LOCK = threading.Lock()


def emit(paper_id, stage, progress):
    labels = {
        "parsing_pages": "🔍 正在识别页面结构...",
        "parsing_text": "📄 正在提取文本内容...",
        "parsing_tables": "📊 正在解析表格...",
        "parsing_done": "✅ 版面解析完成",
        "chunking": "✂️ 正在切分文档...",
        "chunking_done": "✅ 语义分块完成",
        "embedding": "🧠 正在生成向量...",
        "embedding_done": "✅ 向量生成完成",
        "indexing": "💾 正在写入索引...",
        "complete": "🎉 索引完成",
        "error": "❌ 处理失败",
    }
    label = labels.get(stage, stage)
    event = {"stage": stage, "stage_label": label, "progress": progress, "paper_id": paper_id}
    with _PE_LOCK:
        PROCESSING_EVENTS[paper_id] = event
    print(f"[{paper_id[:8]}] {stage}: {progress:.0%}")


def process_background(paper_id, pdf_path, collection, title):
    try:
        emit(paper_id, "parsing_pages", 0.05)
        emit(paper_id, "parsing_text", 0.1)
        emit(paper_id, "parsing_tables", 0.15)
        emit(paper_id, "parsing_done", 0.25)
        emit(paper_id, "chunking", 0.3)

        result = asyncio.run(process_pdf(
            pdf_path=pdf_path,
            paper_id=paper_id,
            collection_name=collection,
            title=title,
            progress_callback=lambda s, p: emit(paper_id, s, p),
        ))
        emit(paper_id, "chunking_done", 0.6)
        emit(paper_id, "embedding", 0.7)
        emit(paper_id, "embedding_done", 0.8)
        emit(paper_id, "indexing", 0.9)

        update_status(paper_id, "ready", chunks_count=result["chunks_count"])
        save_papers()
        emit(paper_id, "complete", 1.0)
        print(f"✅ {title[:40]} → {result['chunks_count']} chunks")
    except Exception as e:
        update_status(paper_id, "error", error=str(e))
        save_papers()
        emit(paper_id, "error", 0)
        print(f"❌ {paper_id}: {e}")


def main():
    # Load papers_db
    if os.path.exists(PAPERS_DB_PATH):
        with open(PAPERS_DB_PATH) as f:
            pdata = json.load(f)
    else:
        print("papers_db.json not found!")
        return

    # Find ready papers
    ready = [p for p in pdata.values() if p["status"] in ("ready", "error")]
    print(f"Found {len(ready)} papers to re-index")

    for paper in ready:
        pid = paper["paper_id"]
        title = paper.get("title", "Unknown")
        pdf_path = paper.get("pdf_path", "")
        collection = paper.get("collection", "papers_v1")

        # Check if PDF exists
        if not os.path.exists(pdf_path):
            print(f"⏭  {pid}: PDF missing ({pdf_path})")
            continue

        print(f"\n📝 Processing: {title[:50]}")
        print(f"   PDF: {pdf_path}")
        print(f"   Collection: {collection}")

        # Run in background
        t = threading.Thread(target=process_background, args=(pid, pdf_path, collection, title))
        t.start()
        time.sleep(2)  # Rate limit

    print("\n⏳ All indexing tasks started. Waiting...")
    # Keep main thread alive
    while threading.active_count() > 1:
        time.sleep(5)


if __name__ == "__main__":
    main()
