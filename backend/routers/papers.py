"""
Router: 论文管理 — 上传/删除/状态/事件/SSE
"""
import asyncio, hashlib, os, re, uuid, json, threading
from pathlib import Path
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pdfplumber

from state import processing_events, _pe_lock, users_db, get_users_db
from data import upsert_paper, update_paper, delete_paper as db_delete_paper, get_paper, get_papers_db, save_users
from config import CHROMADB_DIR, PAPERS_DIR, MINIMAX_API_KEY, MINIMAX_GROUP_ID
from pipeline import process_pdf
from routers.auth import get_current_user

router = APIRouter(prefix="/papers", tags=["papers"])

def _col(user_id: str) -> str:
    return f"user_{user_id.replace('-', '_')}"

class PaperUploadResponse(BaseModel):
    paper_id: str
    title: str
    status: str

class PaperUploadDuplicate(BaseModel):
    duplicate: bool = True
    paper_id: str
    title: str
    status: str

class PaperPatchRequest(BaseModel):
    title: str | None = None
    abstract: str | None = None
    keywords: str | None = None


# ─── 后台任务：处理 PDF ─────────────────────────────
def _process_pdf_background(paper_id: str, pdf_path: str, collection: str, title: str):
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

    try:
        emit("parsing_pages", 0.05)
        emit("parsing_text", 0.1)
        emit("parsing_tables", 0.15)
        emit("parsing_done", 0.25)
        emit("chunking", 0.3)

        result = asyncio.run(process_pdf(
            pdf_path=pdf_path,
            paper_id=paper_id,
            collection_name=collection,
            title=title,
            progress_callback=emit,
        ))
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


# ─── 上传 ────────────────────────────────────────────
@router.post("/upload", response_model=PaperUploadResponse)
async def upload_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_info: tuple = Depends(get_current_user),
):
    user_id, user = user_info
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 文件")

    MAX_FILE_SIZE = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"文件大小超过限制（最大 50MB），当前: {len(content)//1024//1024}MB")

    if user.get("plan") == "free" and len(user.get("papers", [])) >= 20:
        raise HTTPException(429, "免费用户论文上限 20 篇")

    content_hash = _compute_content_hash(content)

    # 检查重复
    existing = [
        (pid, p) for pid, p in get_papers_db().items()
        if p.get("user_id") == user_id and p.get("content_hash") == content_hash
    ]
    if existing:
        dup_pid, dup_info = existing[0]
        dup_title = dup_info.get("title", "")
        dup_status = dup_info.get("status", "")
        need_force_clean = dup_status in ("error", "failed", "processing")
        if not need_force_clean:
            try:
                import chromadb as _cg
                _c = _cg.PersistentClient(path=CHROMADB_DIR)
                _safe = re.sub(r"[^a-zA-Z0-9_]", "_", _col(user_id))
                _ids = _c.get_collection(_safe).get(where={"paper_id": dup_pid})["ids"]
                if not _ids:
                    need_force_clean = True
            except Exception:
                pass
            _pdf = dup_info.get("pdf_path")
            if not need_force_clean and _pdf and not Path(_pdf).exists():
                need_force_clean = True

        if need_force_clean:
            if dup_pid in user.get("papers", []):
                user["papers"].remove(dup_pid)
                save_users()
            try:
                import chromadb as _cg
                _c2 = _cg.PersistentClient(path=CHROMADB_DIR)
                _safe2 = re.sub(r"[^a-zA-Z0-9_]", "_", _col(user_id))
                _col_del = _c2.get_collection(_safe2)
                _col_del.delete(ids=[m for m in _col_del._collection.get()["ids"] if m.startswith(dup_pid)])
            except Exception:
                pass
            db_delete_paper(dup_pid)
        else:
            return PaperUploadDuplicate(
                duplicate=True,
                paper_id=dup_pid,
                title=dup_title,
                status=dup_status,
            )

    paper_id = str(uuid.uuid4())
    title = file.filename.replace(".pdf", "").strip()
    os.makedirs(PAPERS_DIR, exist_ok=True)
    pdf_path = f"{PAPERS_DIR}/{paper_id}.pdf"
    Path(pdf_path).write_bytes(content)

    upsert_paper(paper_id, {
        "paper_id": paper_id,
        "user_id": user_id,
        "title": title,
        "status": "processing",
        "chunks_count": None,
        "content_hash": content_hash,
        "collection": _col(user_id),
        "pdf_path": pdf_path,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
    })
    user["papers"].append(paper_id)
    save_users()

    background_tasks.add_task(_process_pdf_background, paper_id, pdf_path, _col(user_id), title)
    return PaperUploadResponse(paper_id=paper_id, title=title, status="processing")


@router.post("/confirm-upload", response_model=PaperUploadResponse)
async def confirm_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_info: tuple = Depends(get_current_user),
):
    user_id, user = user_info
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 文件")

    MAX_FILE_SIZE = 50 * 1024 * 1024
    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(413, f"文件大小超过限制（最大 50MB），当前: {len(content_bytes)//1024//1024}MB")

    if user.get("plan") == "free" and len(user.get("papers", [])) >= 20:
        raise HTTPException(429, "免费用户论文上限 20 篇")

    content_hash = _compute_content_hash(content_bytes)

    existing = [
        (pid, p) for pid, p in get_papers_db().items()
        if p.get("user_id") == user_id and p.get("content_hash") == content_hash
    ]

    if existing:
        old_pid = existing[0][0]
        p = get_paper(old_pid)
        if p:
            try:
                import chromadb
                c = chromadb.PersistentClient(path=CHROMADB_DIR)
                safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", _col(p["user_id"]))
                col = c.get_collection(safe_name)
                results = col.get(where={"paper_id": old_pid})
                if results["ids"]:
                    col.delete(ids=results["ids"])
            except Exception:
                pass
            db_delete_paper(old_pid)
            if old_pid in user.get("papers", []):
                user["papers"].remove(old_pid)
                save_users()
            pdf_path = p.get("pdf_path")
            if pdf_path and Path(pdf_path).exists():
                Path(pdf_path).unlink()

    paper_id = str(uuid.uuid4())
    title = file.filename.replace(".pdf", "").strip()
    os.makedirs(PAPERS_DIR, exist_ok=True)
    pdf_path = f"{PAPERS_DIR}/{paper_id}.pdf"
    Path(pdf_path).write_bytes(content_bytes)

    upsert_paper(paper_id, {
        "paper_id": paper_id,
        "user_id": user_id,
        "title": title,
        "status": "processing",
        "chunks_count": None,
        "content_hash": content_hash,
        "collection": _col(user_id),
        "pdf_path": pdf_path,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
    })
    user["papers"].append(paper_id)
    save_users()

    background_tasks.add_task(_process_pdf_background, paper_id, pdf_path, _col(user_id), title)
    return PaperUploadResponse(paper_id=paper_id, title=title, status="processing")


# ─── SSE 事件 ───────────────────────────────────────
@router.get("/{paper_id}/events")
async def paper_events(paper_id: str, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
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
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")
    return {
        "paper_id": paper_id,
        "status": p["status"],
        "title": p.get("title", ""),
        "chunks_count": p.get("chunks_count"),
        "error": p.get("error"),
    }


@router.get("/{paper_id}/pdf")
async def paper_pdf(paper_id: str, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")
    pdf_path = p.get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(404, "PDF 文件不存在")
    from fastapi.responses import FileResponse
    return FileResponse(pdf_path, media_type="application/pdf", filename=p.get("title", paper_id) + ".pdf")


@router.get("")
async def list_papers(user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    papers = [
        {
            "paper_id": pid,
            "title": p.get("title", ""),
            "status": p.get("status", ""),
            "chunks_count": p.get("chunks_count"),
            "created_at": p.get("created_at", ""),
            "authors": p.get("authors", ""),
            "year": p.get("year"),
            "journal": p.get("journal", ""),
            "abstract": p.get("abstract", ""),
            "keywords": p.get("keywords", ""),
        }
        for pid, p in get_papers_db().items()
        if p.get("user_id") == user_info[0] and p.get("status") == "ready"
    ]
    return papers


# ─── 删除 / 修改 ────────────────────────────────────
@router.delete("/{paper_id}")
async def delete_paper(paper_id: str, force: bool = False, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
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
    if paper_id in user.get("papers", []):
        user["papers"].remove(paper_id)
        save_users()
    pdf_path = p.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        Path(pdf_path).unlink()
    return {"ok": True}


@router.patch("/{paper_id}")
async def patch_paper(paper_id: str, req: PaperPatchRequest, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")
    update_fields = {}
    if req.title is not None:
        update_fields["title"] = req.title
    if req.abstract is not None:
        update_fields["abstract"] = req.abstract
    if req.keywords is not None:
        update_fields["keywords"] = req.keywords
    if update_fields:
        update_paper(paper_id, **update_fields)
    return {"ok": True}
