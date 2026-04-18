#!/usr/bin/env python3
"""
精准重建脚本 — 只重建 ChromaDB 中缺失的论文
"""
import asyncio, json, logging, os, sys, time, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

BACKEND = Path(__file__).parent
sys.path.insert(0, str(BACKEND))

PAPERS_DB_PATH = "/root/.openclaw/rag-data/papers_db.json"
CHROMADB_PATH = "/root/.openclaw/rag-data/chromadb/chromadb"

from dotenv import load_dotenv
load_dotenv(BACKEND / ".env")

from data import init_papers, get_papers_db, update_paper
from config import CHROMADB_DIR
from pipeline import process_pdf

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
    return callback

def process_one(paper):
    pid = paper["paper_id"]
    title = paper.get("title", "Unknown")
    pdf_path = paper.get("pdf_path", "")
    collection = paper.get("collection", "user_old_bosstest")

    if not pdf_path or not os.path.exists(pdf_path):
        logger.warning(f"⏭ {pid}: PDF 不存在 — {pdf_path}")
        return pid, title, False, 0, "PDF不存在"

    try:
        logger.info(f"▶ {title[:40]}")
        result = asyncio.run(process_pdf(
            pdf_path=pdf_path,
            paper_id=pid,
            collection_name=collection,
            title=title,
            progress_callback=make_callback(pid),
        ))
        chunks = result.get("chunks_count", 0)
        update_paper(pid, status="ready", chunks_count=chunks)
        logger.info(f"✅ {title[:40]} → {chunks} chunks")
        return pid, title, True, chunks, None
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"❌ {pid}: {e}\n{tb[-200:]}")
        update_paper(pid, status="error", error=str(e)[:200])
        return pid, title, False, 0, str(e)


def main():
    # Get papers already in ChromaDB
    import chromadb
    client = chromadb.PersistentClient(path=CHROMADB_PATH)
    try:
        col = client.get_collection("user_old_bosstest")
        existing = set(m["paper_id"] for m in col.get(limit=10000, include=["metadatas"])["metadatas"])
        logger.info(f"ChromaDB 已收录: {len(existing)} 篇")
    except:
        existing = set()

    papers_db = get_papers_db()
    to_index = []
    for pid, p in papers_db.items():
        if pid in existing:
            continue  # Already have chunks
        if p["status"] == "error" and p.get("chunks_count", 0) > 0:
            continue  # Already tried, has chunks (somehow not in ChromaDB)
        pdf_path = p.get("pdf_path", "")
        if not pdf_path or not os.path.exists(pdf_path):
            logger.warning(f"⏭ {pid}: PDF 不存在")
            continue
        to_index.append(p)

    logger.info(f"待索引: {len(to_index)} 篇")

    results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(process_one, p): p for p in to_index}
        for future in as_completed(futures):
            p = futures[future]
            try:
                pid, title, ok, chunks, err = future.result(timeout=600)
                results.append((pid, title, ok, chunks, err))
            except Exception as e:
                logger.error(f"❌ {p['paper_id']}: {e}")
                results.append((p["paper_id"], p.get("title","?"), False, 0, str(e)))

    ok_results = [(pid, title, chunks) for pid, title, ok, chunks, _ in results if ok]
    logger.info(f"\n{'='*50}")
    logger.info(f"完成: {len(ok_results)}/{len(results)} 成功")
    total = sum(c for _, _, c in ok_results)
    logger.info(f"新增 chunks: {total}")
    for pid, title, chunks in ok_results:
        logger.info(f"  ✅ {title[:45]} ({chunks})")
    for pid, title, ok, chunks, err in results:
        if not ok:
            logger.info(f"  ❌ {title[:45]} — {err}")


if __name__ == "__main__":
    main()
