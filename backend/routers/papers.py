"""
Router: 论文管理 — 上传/删除/文件夹/批量移动
Phase 0.8: 文件夹隔离，user_id → folder_id
"""
import asyncio, hashlib, os, re, uuid, json, threading
from pathlib import Path
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, BackgroundTasks, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from state import processing_events, _pe_lock, users_db, get_users_db
from data import (
    upsert_paper, update_paper, delete_paper as db_delete_paper,
    get_paper, get_papers_db, save_users,
    get_user_papers, get_folder_papers, move_papers_to_folder,
)
from folders_db import (
    get_user_folders, get_child_folders, create as create_folder_db,
    rename as rename_folder_db, delete as delete_folder_db,
    count_user_folders,
)
from config import CHROMADB_DIR, PAPERS_DIR, MINIMAX_API_KEY, MINIMAX_GROUP_ID
from pipeline import process_pdf
from routers.auth import get_current_user

router = APIRouter(prefix="/papers", tags=["papers"])

MAX_FOLDER_PER_USER = 100

def _col(user_id: str) -> str:
    return f"user_{user_id.replace('-', '_')}"

# ─── 后台任务：处理 PDF ─────────────────────────────
async def _process_pdf_background(paper_id: str, pdf_path: str, collection: str, title: str):
    def emit(stage: str, progress: float, **kwargs):
        stage_labels = {
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
        label = stage_labels.get(stage, stage)
        event = {"stage": stage, "stage_label": label, "progress": progress, "paper_id": paper_id, **kwargs}
        with _pe_lock:
            processing_events[paper_id] = event

    def _run_sync():
        return asyncio.run(process_pdf(
            pdf_path=pdf_path,
            paper_id=paper_id,
            collection_name=collection,
            title=title,
            progress_callback=emit,
        ))

    try:
        emit("parsing_pages", 0.05)
        emit("parsing_text", 0.1)
        emit("parsing_tables", 0.15)
        emit("parsing_done", 0.25)
        emit("chunking", 0.3)

        # asyncio.to_thread 将 CPU 密集的 PDF 处理卸到线程池，
        # 释放 FastAPI 事件循环，不再阻塞同一 worker 上的其他请求
        result = await asyncio.to_thread(_run_sync)
        emit("chunking_done", 0.6)
        emit("embedding", 0.7)
        emit("embedding_done", 0.8)
        emit("indexing", 0.9)

        pdf_meta = result.get("pdf_metadata", {}) or {}
        display_title = pdf_meta.get('title') or title
        update_fields = {
            "status": "ready",
            "chunks_count": result["chunks_count"],
            "title": display_title,
            "authors": pdf_meta.get('authors', ''),
            "year": pdf_meta.get('year'),
            "journal": pdf_meta.get('journal', ''),
            "doi": pdf_meta.get('doi', ''),
            "abstract": '',
            "keywords": '',
        }
        update_paper(paper_id, **update_fields)
        emit("complete", 1.0, chunks_count=result["chunks_count"])
    except Exception as e:
        update_paper(paper_id, status="error", error=str(e))
        emit("error", 0, error=str(e))
        Path(pdf_path).unlink(missing_ok=True)
    finally:
        def cleanup():
            import time; time.sleep(30)
            processing_events.pop(paper_id, None)
        threading.Thread(target=cleanup, daemon=True).start()


# ─── 工具 ────────────────────────────────────────────
def _compute_content_hash(content: bytes) -> str:
    tmp = f"/tmp/_hash_{uuid.uuid4()}.pdf"
    Path(tmp).write_bytes(content)
    try:
        texts = []
        with pdfplumber.open(tmp) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t and t.strip():
                    texts.append(t.strip())
        return hashlib.sha256(("|||".join(texts)).encode("utf-8")).hexdigest()
    finally:
        Path(tmp).unlink(missing_ok=True)

import pdfplumber

# ─── 批量移动 ──────────────────────────────────────
class MoveRequest(BaseModel):
    paper_ids: list[str]
    target_folder_id: str

@router.post("/move")
async def move_papers(req: MoveRequest, user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    # 验证目标文件夹属于当前用户
    from folders_db import get as get_folder
    target = get_folder(req.target_folder_id)
    if not target or target["user_id"] != user_id:
        raise HTTPException(403, "目标文件夹不存在")
    # 验证所有论文属于当前用户
    papers_db = get_papers_db()
    for pid in req.paper_ids:
        p = papers_db.get(pid)
        if not p or p.get("user_id") != user_id:
            raise HTTPException(403, f"论文 {pid} 不存在或无权操作")
    move_papers_to_folder(req.paper_ids, req.target_folder_id)
    return {"ok": True, "moved": len(req.paper_ids)}


# ─── 文件夹 CRUD ────────────────────────────────────
class CreateFolderRequest(BaseModel):
    name: str
    parent_id: str | None = None

@router.get("/folders")
async def list_folders(user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    folders = get_user_folders(user_id)
    result = []
    for f in folders:
        child_count = len(get_child_folders(f["folder_id"]))
        paper_count = len(get_folder_papers(f["folder_id"]))
        result.append({
            "folder_id": f["folder_id"],
            "name": f["name"],
            "parent_id": f["parent_id"],
            "child_count": child_count,
            "paper_count": paper_count,
        })
    return result

@router.post("/folders")
async def create_folder(req: CreateFolderRequest, user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    if count_user_folders(user_id) >= MAX_FOLDER_PER_USER:
        raise HTTPException(429, f"文件夹数量已达上限（{MAX_FOLDER_PER_USER}个）")
    if req.parent_id:
        parent = get_child_folders(req.parent_id)
        if not any(p["folder_id"] == req.parent_id and p["user_id"] == user_id for p in [{}]):
            parent_folder = next((f for f in get_user_folders(user_id) + list(get_child_folders(req.parent_id)) if f["folder_id"] == req.parent_id), None)
            if not parent_folder or parent_folder["user_id"] != user_id:
                raise HTTPException(403, "父文件夹不存在")
    folder_id = str(uuid.uuid4())
    folder = create_folder_db(folder_id, user_id, req.name, req.parent_id)
    return {"folder_id": folder_id, "name": req.name, "parent_id": req.parent_id}

@router.patch("/folders/{folder_id}")
async def update_folder_name(folder_id: str, req: CreateFolderRequest, user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    from folders_db import get as get_folder
    folder = get_folder(folder_id)
    if not folder or folder["user_id"] != user_id:
        raise HTTPException(404, "文件夹不存在")
    rename_folder_db(folder_id, req.name)
    return {"ok": True}

@router.delete("/folders/{folder_id}")
async def remove_folder(folder_id: str, user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    from folders_db import get as get_folder
    folder = get_folder(folder_id)
    if not folder or folder["user_id"] != user_id:
        raise HTTPException(404, "文件夹不存在")
    # 将内部论文移到默认文件夹
    default_fid = users_db.get(user_id, {}).get("default_folder_id")
    papers_in_folder = get_folder_papers(folder_id)
    if papers_in_folder and default_fid:
        move_papers_to_folder([p["paper_id"] for p in papers_in_folder], default_fid)
    delete_folder_db(folder_id)
    return {"ok": True}


# ─── 上传 ────────────────────────────────────────────
class PaperUploadResponse(BaseModel):
    paper_id: str
    title: str
    status: str
    folder_id: str

@router.post("/upload", response_model=PaperUploadResponse)
async def upload_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    folder_id: str = Form(...),
    user_info: tuple = Depends(get_current_user),
):
    user_id, user = user_info
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 文件")

    # 验证 folder_id
    from folders_db import get as get_folder
    folder = get_folder(folder_id)
    if not folder or folder["user_id"] != user_id:
        raise HTTPException(403, "文件夹不存在")

    MAX_FILE_SIZE = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"文件大小超过限制（最大 50MB），当前: {len(content)//1024//1024}MB")
    if content[:4] != b'%PDF':
        raise HTTPException(400, "文件格式无效：不是有效的 PDF 文件")

    if user.get("plan") == "free":
        user_papers = [p for p in get_papers_db().values() if p.get("user_id") == user_id and p.get("status") == "ready"]
        if len(user_papers) >= 20:
            raise HTTPException(429, "免费用户论文上限 20 篇")

    content_hash = _compute_content_hash(content)

    # 查重（同一用户同一文件夹内）
    folder_papers = get_folder_papers(folder_id)
    existing = [p for p in folder_papers if p.get("content_hash") == content_hash]
    if existing:
        dup = existing[0]
        return PaperUploadResponse(
            paper_id=dup["paper_id"],
            title=dup.get("title", ""),
            status=dup.get("status", ""),
            folder_id=folder_id,
        )

    paper_id = str(uuid.uuid4())
    title = file.filename.replace(".pdf", "").strip()
    os.makedirs(PAPERS_DIR, exist_ok=True)
    pdf_path = f"{PAPERS_DIR}/{paper_id}.pdf"
    Path(pdf_path).write_bytes(content)

    upsert_paper(paper_id, {
        "paper_id": paper_id,
        "user_id": user_id,
        "folder_id": folder_id,
        "title": title,
        "status": "processing",
        "chunks_count": None,
        "content_hash": content_hash,
        "collection": _col(user_id),
        "pdf_path": pdf_path,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
    })

    background_tasks.add_task(_process_pdf_background, paper_id, pdf_path, _col(user_id), title)
    return PaperUploadResponse(paper_id=paper_id, title=title, status="processing", folder_id=folder_id)


# ─── 批量上传 ────────────────────────────────────────
class BatchUploadItem(BaseModel):
    paper_id: str
    title: str
    status: str

class BatchUploadResponse(BaseModel):
    total: int
    papers: list[BatchUploadItem]
    errors: list[str]

class BatchStatusItem(BaseModel):
    paper_id: str
    title: str
    status: str
    chunks_count: int | None
    error: str | None

@router.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload_papers(
    files: list[UploadFile] = File(...),
    folder_id: str = Form(...),
    user_info: tuple = Depends(get_current_user),
):
    """批量上传多个 PDF，同时并行处理"""
    user_id, user = user_info
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")

    from folders_db import get as get_folder
    folder = get_folder(folder_id)
    if not folder or folder["user_id"] != user_id:
        raise HTTPException(403, "文件夹不存在")

    MAX_FILE_SIZE = 50 * 1024 * 1024
    MAX_BATCH = 20
    if len(files) > MAX_BATCH:
        raise HTTPException(400, f"单次最多上传 {MAX_BATCH} 个文件")

    if user.get("plan") == "free":
        user_papers = [p for p in get_papers_db().values() if p.get("user_id") == user_id and p.get("status") == "ready"]
        if len(user_papers) + len(files) > 20:
            raise HTTPException(429, f"免费用户上限 20 篇，此次上传 {len(files)} 篇会超限")

    results: list[BatchUploadItem] = []
    errors: list[str] = []

    for file in files:
        if not file.filename.endswith(".pdf"):
            errors.append(f"{file.filename}: 只支持 PDF 文件")
            continue
        try:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                errors.append(f"{file.filename}: 超过 50MB 限制")
                continue
            if content[:4] != b'%PDF':
                errors.append(f"{file.filename}: 不是有效的 PDF 文件")
                continue

            content_hash = _compute_content_hash(content)

            # 查重（同一文件夹内）
            folder_papers = get_folder_papers(folder_id)
            existing = [p for p in folder_papers if p.get("content_hash") == content_hash]
            if existing:
                dup = existing[0]
                results.append(BatchUploadItem(
                    paper_id=dup["paper_id"],
                    title=dup.get("title", file.filename),
                    status=dup.get("status", "ready"),
                ))
                continue

            paper_id = str(uuid.uuid4())
            title = file.filename.replace(".pdf", "").strip()
            os.makedirs(PAPERS_DIR, exist_ok=True)
            pdf_path = f"{PAPERS_DIR}/{paper_id}.pdf"
            Path(pdf_path).write_bytes(content)

            upsert_paper(paper_id, {
                "paper_id": paper_id,
                "user_id": user_id,
                "folder_id": folder_id,
                "title": title,
                "status": "processing",
                "chunks_count": None,
                "content_hash": content_hash,
                "collection": _col(user_id),
                "pdf_path": pdf_path,
                "error": None,
                "created_at": datetime.utcnow().isoformat(),
            })
            # 立即触发后台处理（不等待）
            import asyncio
            asyncio.get_event_loop().run_in_executor(
                None, _process_pdf_background, paper_id, pdf_path, _col(user_id), title
            )
            results.append(BatchUploadItem(
                paper_id=paper_id,
                title=title,
                status="processing",
            ))
        except Exception as e:
            errors.append(f"{file.filename}: {str(e)[:50]}")

    return BatchUploadResponse(total=len(results), papers=results, errors=errors)


@router.get("/batch-status")
async def batch_status(
    ids: str = "",  # comma-separated paper_ids
    user_info: tuple = Depends(get_current_user),
):
    """批量查询论文状态（前端轮询用）"""
    _, _ = user_info
    if not ids:
        return []
    paper_ids = [x.strip() for x in ids.split(",") if x.strip()]
    papers_db = get_papers_db()
    return [
        {
            "paper_id": pid,
            "title": papers_db[pid].get("title", "") if pid in papers_db else "",
            "status": papers_db[pid].get("status", "") if pid in papers_db else "unknown",
            "chunks_count": papers_db[pid].get("chunks_count") if pid in papers_db else None,
            "error": papers_db[pid].get("error") if pid in papers_db else None,
        }
        for pid in paper_ids
    ]


# ─── SSE 事件 ───────────────────────────────────────
@router.get("/{paper_id}/events")
async def paper_events(paper_id: str, user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_id:
        raise HTTPException(404, "论文不存在")

    async def event_generator():
        if p["status"] == "ready":
            yield f"data: {json.dumps({'stage':'complete','progress':1.0,'paper_id':paper_id,'chunks_count':p.get('chunks_count')})}\n\n"
            return
        if p["status"] == "error":
            yield f"data: {json.dumps({'stage':'error','progress':0,'paper_id':paper_id,'error':p.get('error','')})}\n\n"
            return
        for _ in range(300):
            event = processing_events.get(paper_id)
            if event:
                yield f"data: {json.dumps(event)}\n\n"
                if event["stage"] in ("complete", "error"):
                    break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ─── 状态 / PDF / 列表 ──────────────────────────────
@router.get("/{paper_id}/status")
async def paper_status(paper_id: str, user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_id:
        raise HTTPException(404, "论文不存在")
    return {
        "paper_id": paper_id,
        "status": p.get("status", ""),
        "title": p.get("title", ""),
        "folder_id": p.get("folder_id"),
        "chunks_count": p.get("chunks_count"),
        "error": p.get("error"),
    }

@router.get("/{paper_id}/pdf")
async def paper_pdf(paper_id: str, user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_id:
        raise HTTPException(404, "论文不存在")
    pdf_path = p.get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(404, "PDF 文件不存在")
    from fastapi.responses import FileResponse
    return FileResponse(pdf_path, media_type="application/pdf", filename=p.get("title", paper_id) + ".pdf")

@router.get("")
async def list_papers(folder_id: str | None = None, user_info: tuple = Depends(get_current_user)):
    """列出论文，支持按 folder_id 过滤"""
    user_id, _ = user_info
    if folder_id:
        from folders_db import get as get_folder
        folder = get_folder(folder_id)
        if not folder or folder["user_id"] != user_id:
            raise HTTPException(403, "文件夹不存在")
        papers = get_folder_papers(folder_id)
    else:
        papers = get_user_papers(user_id)
    return [
        {
            "paper_id": p["paper_id"],
            "folder_id": p.get("folder_id"),
            "title": p.get("title", ""),
            "status": p.get("status", ""),
            "created_at": p.get("created_at", ""),
            "authors": p.get("authors", ""),
            "year": p.get("year"),
            "journal": p.get("journal", ""),
            "doi": p.get("doi", ""),
        }
        for p in papers
        if p.get("user_id") == user_id and p.get("status") == "ready"
    ]


# ─── 删除 / 修改 ────────────────────────────────────
@router.delete("/{paper_id}")
async def delete_paper(paper_id: str, force: bool = False, user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_id:
        raise HTTPException(404, "论文不存在")
    if p.get("status") == "processing" and not force:
        raise HTTPException(409, "论文正在处理中，使用 ?force=true 强制删除")
    try:
        import chromadb
        c = chromadb.PersistentClient(path=CHROMADB_DIR)
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", _col(p["user_id"]))
        col = c.get_collection(safe_name)
        results = col.get(where={"paper_id": paper_id})
        if results["ids"]:
            col.delete(ids=results["ids"])
    except Exception:
        pass
    db_delete_paper(paper_id)
    pdf_path = p.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        Path(pdf_path).unlink()
    return {"ok": True}

class PaperPatchRequest(BaseModel):
    title: str | None = None

@router.patch("/{paper_id}")
async def patch_paper(paper_id: str, req: PaperPatchRequest, user_info: tuple = Depends(get_current_user)):
    user_id, _ = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_id:
        raise HTTPException(404, "论文不存在")
    if req.title is not None:
        update_paper(paper_id, title=req.title)
    return {"ok": True}
