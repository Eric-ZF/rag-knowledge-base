#!/usr/bin/env python3
"""
重建 ChromaDB 索引 — 独立运行脚本
"""
import asyncio
import json
import logging
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

BACKEND = Path(__file__).parent
sys.path.insert(0, str(BACKEND))

PAPERS_DB_PATH = "/root/.openclaw/rag-data/papers_db.json"

# Load .env
from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")

from data import init_papers, get_papers_db, update_paper
from config import CHROMADB_DIR
from pipeline import process_pdf

# Init data layer
init_papers()

STAGE_LABELS = {
    "parsing_pages": "🔍 识别页面结构",
    "parsing_text": "📄 提取文本",
    "parsing_tables": "📊 解析表格",
    "parsing_done": "✅ 版面解析完成",
    "chunking": "✂️ 切分文档",
    "chunking_done": "✅ 语义分块完成",
    "embedding": "🧠 生成向量",
    "embedding_done": "✅ 向量生成完成",
    "indexing": "💾 写入索引",
    "complete": "🎉 索引完成",
    "error": "❌ 处理失败",
}


def make_callback(paper_id):
    def callback(stage, progress, **kwargs):
        label = STAGE_LABELS.get(stage, stage)
        logger.info(f"  [{paper_id[:8]}] {label} {progress:.0%}")
        if kwargs:
            logger.info(f"  [{paper_id[:8]}] extra: {kwargs}")
    return callback


def process_one(paper):
    pid = paper["paper_id"]
    title = paper.get("title", "Unknown")
    pdf_path = paper.get("pdf_path", "")
    collection = paper.get("collection", "papers_v1")
    
    if not pdf_path or not os.path.exists(pdf_path):
        logger.warning(f"⏭ {pid}: PDF 不存在 — {pdf_path}")
        return pid, title, False, 0, "PDF不存在"
    
    try:
        logger.info(f"▶ 开始: {title[:40]}")
        result = asyncio.run(process_pdf(
            pdf_path=pdf_path,
            paper_id=pid,
            collection_name=collection,
            title=title,
            progress_callback=make_callback(pid),
        ))
        chunks = result.get("chunks_count", 0)
        update_paper(pid, status="ready", chunks_count=chunks)
        logger.info(f"✅ 完成: {title[:40]} → {chunks} chunks")
        return pid, title, True, chunks, None
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"❌ {pid}: {e}\n{tb[-300:]}")
        update_paper(pid, status="error", error=str(e)[:200])
        return pid, title, False, 0, str(e)


def main():
    papers_db = get_papers_db()
    papers = list(papers_db.values())
    
    # Papers that need indexing (have PDF and are ready/error)
    to_index = []
    for p in papers:
        if p["status"] not in ("ready", "error"):
            continue
        to_index.append(p)
    
    logger.info(f"共 {len(to_index)} 篇论文待索引")
    
    MAX_WORKERS = 2
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_one, p): p for p in to_index}
        
        for future in as_completed(futures):
            p = futures[future]
            try:
                pid, title, ok, chunks, err = future.result(timeout=600)
                results.append((pid, title, ok, chunks, err))
            except Exception as e:
                logger.error(f"❌ {p['paper_id']}: {e}")
                results.append((p["paper_id"], p.get("title","?"), False, 0, str(e)))
    
    # Summary
    ok_results = [(pid, title, chunks) for pid, title, ok, chunks, _ in results if ok]
    logger.info(f"\n{'='*50}")
    logger.info(f"索引重建完成: {len(ok_results)}/{len(results)} 成功")
    total = sum(c for _, _, c in ok_results)
    logger.info(f"总 chunks: {total}")
    for pid, title, chunks in ok_results:
        logger.info(f"  ✅ {title[:45]} ({chunks})")
    for pid, title, ok, chunks, err in results:
        if not ok:
            logger.info(f"  ❌ {title[:45]} — {err}")


if __name__ == "__main__":
    main()
