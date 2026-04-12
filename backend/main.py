"""
Phase 0.6 — FastAPI 入口
papers_db + users_db 全部持久化为 JSON，重启不丢失。
"""

import chromadb, os, re, uuid, json, asyncio, threading
from datetime import datetime
from pathlib import Path
from typing import Generator, Literal

from dotenv import load_dotenv
load_dotenv()

# ─── helpers ─────────────────────────────────────────────
def _col(user_id: str) -> str:
    """永远用公式生成 collection 名，不要从 DB 里读（避免脏数据）"""
    return f"user_{user_id.replace('-', '_')}"

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import create_access_token, verify_token, hash_password, verify_password
from config import validate_minimax_chat_config, MINIMAX_API_KEY, MINIMAX_GROUP_ID, CHROMADB_DIR, PAPERS_DIR, CHAT_MODEL
from data import (
    init_papers, init_users,
    get_paper, upsert_paper, update_paper, delete_paper,
    get_user_papers, get_papers_db,
    save_users,
)
from pipeline import process_pdf, search_chunks
from chat import generate_answer_with_self_eval as generate_answer, MiniMaxChatClient
from feedback import get_feedback_store, SCORE_THRESHOLD

# ─── 启动验证 ─────────────────────────────────────────
try:
    validate_minimax_chat_config()
except RuntimeError as e:
    print(f"⚠️  {e}")

# ─── 数据层初始化（从 JSON 恢复）────────────────────
init_papers()
users_db, users_by_email = init_users()

# ─── Lifespan：启动时预加载 embedding 模型 ─────────────────
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 写启动标记，watchdog 据此判断是否在 startup 中
    Path("/tmp/backend_starting").write_text("1")
    # BGE 模型改为惰性加载（首次使用时加载），不预加载以节省 1.3GB 常驻内存
    # ── 启动 phantom 检测：papers_db vs ChromaDB 对账 ──
    print("🔍 启动 phantom 检测...")
    from data import get_papers_db
    papers_db = get_papers_db()
    import chromadb
    phantom_count = 0
    for paper_id, p in papers_db.items():
        if p.get("status") == "ready":
            try:
                _client = chromadb.PersistentClient(path=CHROMADB_DIR)
                safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", _col(p["user_id"]))
                col = _client.get_collection(safe_name)
                results = col.get(where={"paper_id": paper_id})
                if not results["ids"]:
                    from data import update_paper
                    update_paper(paper_id, status="error", error="索引丢失，请重新上传")
                    print(f"  ⚠️ [{paper_id[:8]}] Phantom 检测到：ChromaDB 无 chunks，标记为 error")
                    phantom_count += 1
            except Exception as e:
                print(f"  ⚠️ [{paper_id[:8]}] Phantom 检测失败: {e}")
    print(f"🔍 Phantom 检测完成：{phantom_count} 篇标记为 error")

    # ── 启动孤立 PDF 清理：papers_dir 中无对应记录的 PDF ──
    print("🗑️ 启动孤立 PDF 清理...")
    orphan_deleted = 0
    papers_dir_path = Path(PAPERS_DIR)
    for pdf_file in papers_dir_path.glob("*.pdf"):
        pid = pdf_file.stem  # filename without .pdf
        if pid not in papers_db:
            try:
                pdf_file.unlink()
                print(f"  🗑️ 孤立 PDF 已删除: {pdf_file.name}")
                orphan_deleted += 1
            except Exception as e:
                print(f"  ⚠️ 删除失败 {pdf_file.name}: {e}")
    print(f"🗑️ 孤立 PDF 清理完成：删除 {orphan_deleted} 个残留文件")

    Path("/tmp/backend_starting").write_text("0")  # startup 完成
    print("✅ Embedding 模型就绪，uvicorn 开始接受请求")
    yield
    # shutdown 清理（暂无）
    Path("/tmp/backend_starting").write_text("0")

# ─── SSE 索引进度（全局事件总线）────────────────────
# paper_id → {"stage": str, "progress": float, "chunks_count": int|None, "error": str|None}
processing_events: dict[str, dict] = {}
_pe_lock = threading.Lock()  # 保护 processing_events 并发写入

# ─── FastAPI ─────────────────────────────────────────
app = FastAPI(
    title="RAG 学术知识库 — Phase 0.6",
    version="0.6.0",
    lifespan=lifespan,
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic 模型 ────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    collection_name: str | None = None
    top_k: int = 8
    mode: Literal["default", "methodology", "survey"] = "default"
    paper_ids: list[str] | None = None  # 可选，限定检索范围

class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]
    meta: dict = {}

class PaperUploadResponse(BaseModel):
    paper_id: str
    title: str
    status: str

class PaperUploadDuplicate(BaseModel):
    duplicate: bool = True
    paper_id: str
    title: str
    status: str  # "ready" | "processing"

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str


# ─── 健康检查 ─────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "phase": "phase0.7",
        "model": f"{CHAT_MODEL} + Jina AI embedding",
        "minimax_configured": bool(MINIMAX_API_KEY and MINIMAX_GROUP_ID),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─── 认证 ─────────────────────────────────────────────
@app.post("/auth/register")
async def register(req: RegisterRequest):
    email, password = req.email, req.password
    if email in users_by_email:
        raise HTTPException(400, "邮箱已注册")
    user_id = str(uuid.uuid4())
    collection_name = f"user_{user_id.replace('-', '_')}"
    user_record = {
        "email": email,
        "user_id": user_id,
        "password": hash_password(password),  # bcrypt 哈希存储
        "plan": "free",
        "collection": _col(user_id),
    }
    users_db[user_id] = user_record
    users_by_email[email] = user_record
    _save_users()
    return {"user_id": user_id, "collection": collection_name}


@app.post("/auth/login")
async def login(req: LoginRequest):
    email, password = req.email, req.password
    user = users_by_email.get(email)
    if not user or not verify_password(password, user["password"]):
        raise HTTPException(401, "邮箱或密码错误")
    token = create_access_token({"sub": email, "user_id": user["user_id"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "collection": _col(user["user_id"]),
        "plan": user["plan"],
    }


def _save_users() -> None:
    from data import _save_users as _su
    _su(users_db)


def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "未提供认证信息")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(401, "无效的认证方式")
        payload = verify_token(token)
        email, user_id = payload["sub"], payload.get("user_id")
        if not user_id or user_id not in users_db:
            raise HTTPException(401, "用户不存在")
        return user_id, users_db[user_id]
    except (ValueError, KeyError):
        raise HTTPException(401, "无效的 Token")


# ─── 后台任务：处理 PDF ───────────────────────────────
def _process_pdf_background(paper_id: str, pdf_path: str, collection: str, title: str):
    def emit(stage: str, progress: float, **kwargs):
        """向 SSE 总线推送进度（细化阶段）"""
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
        import asyncio
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
        # 提取 PDF 元数据，用 Docling 解析出的标题覆盖文件名标题
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
            # Fix 7: 摘要和关键词占位（后续可编辑）
            "abstract": '',
            "keywords": '',
        }
        update_paper(paper_id, **update_fields)
        emit("complete", 1.0, chunks_count=result["chunks_count"])
        print(f"[{paper_id}] ✅ 索引完成，{result['chunks_count']} chunks, title={display_title[:40]}")
    except Exception as e:
        update_paper(paper_id, status="error", error=str(e))
        emit("error", 0, error=str(e))
        print(f"[{paper_id}] ❌ 索引失败: {e}，PDF 残留已清理")
        Path(pdf_path).unlink(missing_ok=True)
    finally:
        # PDF 保留在持久化路径，不删除
        # 处理完成后延迟清理事件（给 SSE 留时间推送）
        import threading
        def cleanup():
            import time; time.sleep(30)
            processing_events.pop(paper_id, None)
        threading.Thread(target=cleanup, daemon=True).start()


# ─── PDF 上传 ────────────────────────────────────────
@app.post("/papers/upload", response_model=PaperUploadResponse)
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

    if user["plan"] == "free" and len(user["papers"]) >= 20:
        raise HTTPException(429, "免费用户论文上限 20 篇")

    # ── 内容去重：计算 SHA256 并检查是否已上传 ─────────
    import hashlib, pdfplumber
    tmp_check_path = f"/tmp/_check_{uuid.uuid4()}.pdf"
    Path(tmp_check_path).write_bytes(content)
    try:
        texts = []
        with pdfplumber.open(tmp_check_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t and t.strip():
                    texts.append(t.strip())
        content_hash = hashlib.sha256(("|||".join(texts)).encode("utf-8")).hexdigest()
    finally:
        Path(tmp_check_path).unlink(missing_ok=True)

    # 检查是否已上传过相同内容（content_hash 精确匹配）
    existing = [
        (pid, p) for pid, p in get_papers_db().items()
        if p.get("user_id") == user_id and p.get("content_hash") == content_hash
    ]
    if existing:
        dup_pid, dup_info = existing[0]
        dup_title = dup_info.get("title", "")
        dup_status = dup_info.get("status", "")
        # ── Fix 2: 扩展残留检测 ────────────────────────────────────
        # 1. error/failed/processing → 自动清除（上次中途失败的遗留）
        # 2. status=ready 但 ChromaDB 无 chunks → 孤立残留，清除重新索引
        # 3. status=ready 但 PDF 文件不存在 → 孤立残留，清除重新上传
        need_force_clean = dup_status in ("error", "failed", "processing")
        if not need_force_clean:
            # 检查 ChromaDB 是否有对应 chunks
            try:
                import chromadb as _cg
                _c = _cg.PersistentClient(path=CHROMADB_DIR)
                _safe = re.sub(r"[^a-zA-Z0-9_]", "_", _col(user_id))
                _col_check = _c.get_collection(_safe)
                _ids = _col_check.get(where={"paper_id": dup_pid})["ids"]
                if not _ids:
                    print(f"[{dup_pid}] 检测到孤立残留（status=ready 但 ChromaDB 无 chunks），清除后重新索引...")
                    need_force_clean = True
            except Exception:
                pass  # ChromaDB 出错暂不清理
            # 检查 PDF 是否存在
            _pdf = dup_info.get("pdf_path")
            if not need_force_clean and _pdf and not Path(_pdf).exists():
                print(f"[{dup_pid}] 检测到孤立残留（status=ready 但 PDF 文件不存在），清除后重新上传...")
                need_force_clean = True

        if need_force_clean:
            print(f"[{dup_pid}] 清除重复论文残留（status={dup_status}）...")
            if dup_pid in user["papers"]:
                user["papers"].remove(dup_pid)
                save_users()
            try:
                import chromadb as _cg
                _c2 = _cg.PersistentClient(path=CHROMADB_DIR)
                _safe2 = re.sub(r"[^a-zA-Z0-9_]", "_", _col(user_id))
                _col_del = _c2.get_collection(_safe2)
                _col_del.delete(ids=[mid for mid in _col_del._collection.get()["ids"] if mid.startswith(dup_pid)])
            except Exception:
                pass
            delete_paper(dup_pid)
            # 清除后继续正常上传流程（不再 return）
        else:
            # status=ready 且 ChromaDB 有 chunks 且 PDF 存在 → 返回前端确认
            return PaperUploadDuplicate(
                duplicate=True,
                paper_id=dup_pid,
                title=dup_title,
                status=dup_status,
            )

    paper_id = str(uuid.uuid4())
    title = file.filename.replace(".pdf", "").strip()

    # PDF 持久化存储（不在 /tmp，避免重启丢失）
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
        "pdf_path": pdf_path,  # 持久化路径，供 PDF 下载 endpoint 使用
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
    })
    user["papers"].append(paper_id)
    _save_users()

    # 后台任务直接读持久化路径，不需要 /tmp
    background_tasks.add_task(_process_pdf_background, paper_id, pdf_path, _col(user_id), title)
    return PaperUploadResponse(paper_id=paper_id, title=title, status="processing")



@app.post("/papers/confirm-upload", response_model=PaperUploadResponse)
async def confirm_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_info: tuple = Depends(get_current_user),
):
    """
    强制重新上传（用于：用户确认覆盖重复论文）。
    
    流程：1) 先删除旧论文（force=True）→ 2) 重新上传新 PDF。
    同时发送 both file + confirm=true 时触发此流程。
    """
    user_id, user = user_info
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 文件")

    MAX_FILE_SIZE = 50 * 1024 * 1024
    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(413, f"文件大小超过限制（最大 50MB），当前: {len(content_bytes)//1024//1024}MB")

    if user["plan"] == "free" and len(user["papers"]) >= 20:
        raise HTTPException(429, "免费用户论文上限 20 篇")

    # 计算 content_hash 并找旧记录
    import hashlib, pdfplumber
    tmp_path = f"/tmp/_confirm_{uuid.uuid4()}.pdf"
    Path(tmp_path).write_bytes(content_bytes)
    try:
        texts = []
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t and t.strip():
                    texts.append(t.strip())
        content_hash = hashlib.sha256(("|||".join(texts)).encode("utf-8")).hexdigest()
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    existing = [
        (pid, p) for pid, p in get_papers_db().items()
        if p.get("user_id") == user_id and p.get("content_hash") == content_hash
    ]

    # 强制删除旧记录（包括 ChromaDB + papers_db + PDF）
    if existing:
        old_pid = existing[0][0]
        print(f"[confirm_upload] 检测到旧论文 {old_pid}，强制删除...")
        # 复用 delete_paper_endpoint 逻辑，但用内部方式（非 HTTP）
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
                    print(f"[confirm_upload] ChromaDB 删除 {len(results['ids'])} chunks")
            except Exception as e:
                print(f"[confirm_upload] ChromaDB 删除失败: {e}")
            from papers_db import delete as papers_db_delete
            papers_db_delete(old_pid)
            print(f"[confirm_upload] papers_db 删除完成")
            if old_pid in user["papers"]:
                user["papers"].remove(old_pid)
                _save_users()
            pdf_path = p.get("pdf_path")
            if pdf_path and Path(pdf_path).exists():
                Path(pdf_path).unlink()
                print(f"[confirm_upload] PDF 文件已删除")

    # 上传新 PDF
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
    _save_users()

    background_tasks.add_task(_process_pdf_background, paper_id, pdf_path, _col(user_id), title)
    print(f"[confirm_upload] ✅ 新论文 {paper_id} 开始索引: {title}")
    return PaperUploadResponse(paper_id=paper_id, title=title, status="processing")


@app.get("/papers/{paper_id}/events")
async def paper_events(paper_id: str, user_info: tuple = Depends(get_current_user)):
    """SSE 实时推送论文索进进度"""
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")

    async def event_generator():
        # 已完成的直接发
        if p["status"] == "ready":
            yield f"data: {json.dumps({'stage':'complete','progress':1.0,'paper_id':paper_id,'chunks_count':p.get('chunks_count')})}\n\n"
            return
        if p["status"] == "error":
            yield f"data: {json.dumps({'stage':'error','progress':0,'paper_id':paper_id,'error':p.get('error','')})}\n\n"
            return

        # 轮询 processing_events 直到完成
        for _ in range(300):  # 最多 5 分钟
            event = processing_events.get(paper_id)
            if event:
                yield f"data: {json.dumps(event)}\n\n"
                if event["stage"] in ("complete", "error"):
                    break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/papers/{paper_id}/status")
async def paper_status(paper_id: str, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")

    # 合并 paper 状态 + processing_events 细粒度阶段
    resp = {
        "paper_id": paper_id,
        "title": p["title"],
        "status": p["status"],
        "chunks_count": p.get("chunks_count"),
        "error": p.get("error"),
    }

    # 如果正在处理中，从内存事件总线拿细粒度阶段（前端进度条文字）
    if p["status"] == "processing":
        event = processing_events.get(paper_id)
        if event:
            resp["stage"] = event.get("stage", "processing")
            resp["stage_label"] = event.get("stage_label", "正在处理中…")
            resp["progress"] = event.get("progress", 0)
        else:
            resp["stage"] = "processing"
            resp["stage_label"] = "正在处理中…"
            resp["progress"] = 0

    return resp


@app.get("/papers/{paper_id}/pdf")
async def get_paper_pdf(paper_id: str, user_info: tuple = Depends(get_current_user)):
    """下载论文 PDF 文件，支持浏览器 PDF 插件直接预览"""
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")
    pdf_path = p.get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(404, "PDF 文件不存在，可能尚未处理完成")
    from fastapi.responses import FileResponse
    return FileResponse(
        path=pdf_path,
        filename=f"{p['title']}.pdf",
        media_type="application/pdf",
    )


@app.get("/papers")
async def list_papers(user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    results = []
    for pid in user["papers"]:
        p = get_paper(pid)
        if not p:
            continue
        # 从 ChromaDB 查询实际 chunk 数量（papers_db 的 chunks_count 可能为 None）
        try:
            import chromadb
            client = chromadb.PersistentClient(path=CHROMADB_DIR)
            safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", _col(p["user_id"]))
            col = client.get_collection(safe_name)
            ids = col.get(where={"paper_id": pid})["ids"]
            count = len(ids) if ids else 0
        except Exception:
            count = p.get("chunks_count") or 0
        results.append({
            "paper_id": pid,
            "title": p.get("title") or "",
            "authors": p.get("authors") or "",
            "year": p.get("year"),
            "journal": p.get("journal") or "",
            "doi": p.get("doi") or "",
            "status": p.get("status") or "unknown",
            "chunks_count": count,
            "created_at": p.get("created_at", ""),
            "deletable": p.get("status") != "processing",
            # Fix 7: 返回摘要和关键词（前端可展示）
            "abstract": p.get("abstract") or "",
            "keywords": p.get("keywords") or "",
        })
    return results


@app.delete("/papers/{paper_id}")
async def delete_paper_endpoint(
    paper_id: str,
    force: bool = False,
    user_info: tuple = Depends(get_current_user),
):
    """
    删除论文：ChromaDB chunks → papers_db → PDF 文件，三级彻底清除。
    
    force=True 时，即使是 processing 状态也强制删除（用于清理 stuck job）。
    """
    user_id, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_id:
        raise HTTPException(404, "论文不存在")
    
    # processing 状态：默认拒绝，force=True 时允许
    if p["status"] == "processing" and not force:
        raise HTTPException(409, "论文正在处理中，无法删除。传入 ?force=true 可强制删除。")

    # 1. 从 ChromaDB 删除 chunks
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMADB_DIR)
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", _col(p["user_id"]))
        col = client.get_collection(safe_name)
        results = col.get(where={"paper_id": paper_id})
        if results["ids"]:
            col.delete(ids=results["ids"])
            print(f"[{paper_id}] 🗑️ ChromaDB 删除 {len(results['ids'])} chunks")
    except Exception as e:
        print(f"[{paper_id}] ⚠️ ChromaDB 删除失败: {e}")

    # 2. 从 papers_db 彻底删除记录（调用 papers_db 模块的 delete，非 endpoint）
    try:
        from papers_db import delete as papers_db_delete
        papers_db_delete(paper_id)
        print(f"[{paper_id}] 🗑️ papers_db 记录已删除")
    except Exception as e:
        print(f"[{paper_id}] ⚠️ papers_db 删除失败: {e}")

    # 3. 从用户论文列表移除
    if paper_id in user["papers"]:
        user["papers"].remove(paper_id)
        _save_users()

    # 4. 删除持久化的 PDF 文件
    pdf_path = p.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        Path(pdf_path).unlink()
        print(f"[{paper_id}] 🗑️ PDF 文件已删除: {pdf_path}")

    return {"ok": True, "paper_id": paper_id, "title": p.get("title", ""),
            "chunks_removed": len(results.get("ids", [])) if "results" in dir() else None}

    return {"ok": True, "paper_id": paper_id, "title": p["title"]}


# ─── 论文元数据编辑 ───────────────────────────────────
class PaperUpdateRequest(BaseModel):
    title: str | None = None
    abstract: str | None = None
    keywords: str | None = None

@app.patch("/papers/{paper_id}")
async def update_paper_metadata(
    paper_id: str,
    req: PaperUpdateRequest,
    user_info: tuple = Depends(get_current_user),
):
    """编辑论文的 title / abstract / keywords"""
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")

    updates = {}
    if req.title is not None:
        updates["title"] = req.title.strip()
    if req.abstract is not None:
        updates["abstract"] = req.abstract.strip()
    if req.keywords is not None:
        updates["keywords"] = req.keywords.strip()

    if not updates:
        raise HTTPException(400, "没有需要更新的字段")

    update_paper(paper_id, **updates)
    return {"ok": True, "paper_id": paper_id, "updated": list(updates.keys())}


# ─── RAG 问答 ─────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")

    collection = req.collection_name or user["collection"]
    t0 = time.monotonic()

    # 只查询 status=ready 的论文
    ready = [
        pid for pid in user["papers"]
        if (p := get_paper(pid)) and p["status"] == "ready"
    ]
    if not ready:
        return ChatResponse(
            answer="你的论文库还没有已索引的论文，请先上传 PDF 并等待索引完成。",
            citations=[],
            meta={"mode": req.mode, "paper_count": 0, "chunk_count": 0},
        )

    # paper_ids 过滤
    target_pids = set(ready)
    if req.paper_ids:
        target_pids = target_pids & set(req.paper_ids)
        if not target_pids:
            return ChatResponse(
                answer="指定的论文不在你的论文库中或尚未索引。",
                citations=[],
                meta={"mode": req.mode, "paper_count": 0, "chunk_count": 0},
            )

    # ── Step 1: 相似问题检测 ────────────────────────
    feedback_store = get_feedback_store()
    similar = feedback_store.find_similar(req.question)
    has_similar_history = len(similar) > 0

    # survey 模式需要更多 chunks
    effective_top_k = max(req.top_k * 5, 20) if req.mode == "survey" else req.top_k

    # ── Step 2: 检索（自适应 top_k） ─────────────────
    t1 = time.monotonic()
    chunks = await search_chunks(
        query=req.question,
        collection_name=collection,
        top_k=effective_top_k,
    )
    embedding_ms = (time.monotonic() - t1) * 1000

    if req.paper_ids:
        chunks = [c for c in chunks if c["paper_id"] in target_pids]

    if not chunks:
        total_ms = (time.monotonic() - t0) * 1000
        print(f"[/chat] ⚠️ 无相关 chunks，检索耗时 {embedding_ms:.0f}ms，总耗时 {total_ms:.0f}ms")
        return ChatResponse(
            answer="抱歉，我在你的论文库中没有找到相关内容。",
            citations=[],
            meta={"mode": req.mode, "paper_count": 0, "chunk_count": 0},
        )

    # ── Step 3: 生成答案（带自我打分） ─────────────
    t2 = time.monotonic()
    try:
        answer_text, citations, meta = await generate_answer(
            question=req.question,
            chunks=chunks,
            mode=req.mode,
        )
        llm_ms = (time.monotonic() - t2) * 1000
        total_ms = (time.monotonic() - t0) * 1000

        self_eval = meta.get("self_eval", {})
        score = self_eval.get("total", 100)

        # ── Step 4: 差评记录 ─────────────────────────
        quality_warning = None
        if score < SCORE_THRESHOLD:
            feedback_store.add_failed(
                question=req.question,
                answer=answer_text,
                scores=self_eval,
                chunks_count=len(chunks),
                retrieval_strategy="default",
            )
            quality_warning = f"⚠️ 答案质量偏低（{score}/100），已记录用于改进检索策略。"

        print(f"[/chat] ✅ 回答生成 | 检索: {embedding_ms:.0f}ms | LLM: {llm_ms:.0f}ms | "
              f"总分: {score} | chunks: {len(chunks)} | 论文数: {meta.get('paper_count',0)}"
              f"{' | ' + quality_warning if quality_warning else ''}")

        meta["timing_ms"] = {"embedding": round(embedding_ms), "llm": round(llm_ms), "total": round(total_ms)}
        if quality_warning:
            meta["quality_warning"] = quality_warning

        return ChatResponse(answer=answer_text, citations=citations, meta=meta)

    except Exception as e:
        total_ms = (time.monotonic() - t0) * 1000
        err_msg = str(e)
        # MiniMax 超时/网络错误 → 返回友好提示，不崩服务
        is_timeout = any(kw in err_msg.lower() for kw in ["timeout", "timed out", "connection", "网络", "超时"])
        is_minimax_fail = any(kw in err_msg for kw in ["MiniMax", "429", "502", "503", "504", "529"])
        if is_timeout or is_minimax_fail or "read timeout" in err_msg.lower():
            print(f"[/chat] ⚠️ MiniMax 调用失败（不崩服务）| 检索: {embedding_ms:.0f}ms | "
                  f"总耗时: {total_ms:.0f}ms | 错误: {err_msg[:100]}")
            return ChatResponse(
                answer="⚠️ AI 服务响应超时（MiniMax 引擎不稳定），请稍后重试。\n\n"
                       "如果持续出现此问题，可能是网络拥堵，可尝试：\n"
                       "• 换个时间再试\n"
                       "• 减少同时在线人数\n"
                       "• 腾讯云服务器带宽临时瓶颈（非系统问题）",
                citations=[],
                meta={"mode": req.mode, "error": "timeout", "retrieval_ms": round(embedding_ms),
                      "timing_ms": {"embedding": round(embedding_ms), "total": round(total_ms)}},
            )
        # 其他未知错误 → 返回友好提示
        print(f"[/chat] ❌ 生成失败 | 检索: {embedding_ms:.0f}ms | 总耗时: {total_ms:.0f}ms | 错误: {err_msg}")
        return ChatResponse(
            answer=f"⚠️ 生成答案时遇到问题：{err_msg[:100]}\n\n请稍后重试，或联系管理员排查。",
            citations=[],
            meta={"mode": req.mode, "error": "unknown", "timing_ms": {"embedding": round(embedding_ms), "total": round(total_ms)}},
        )


# ─── SSE 流式聊天（解决代理超时）───────────────────────
@app.post("/chat/stream")
async def chat_stream(req: ChatRequest, user_info: tuple = Depends(get_current_user)):
    """
    流式版本 /chat/stream — 每个 token 立即推送，
    前端边收边显示，代理看到持续数据传输不会超时。
    """
    _, user = user_info
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")

    collection = req.collection_name or user["collection"]

    # 只查询 status=ready 的论文
    ready = [
        pid for pid in user["papers"]
        if (p := get_paper(pid)) and p["status"] == "ready"
    ]
    if not ready:
        async def empty():
            yield "data: " + json.dumps({"type": "done", "answer": "你的论文库还没有已索引的论文，请先上传 PDF。"}) + "\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    target_pids = set(ready)
    if req.paper_ids:
        target_pids = target_pids & set(req.paper_ids)

    # 检索 chunks（与 /chat 相同）
    t0 = time.monotonic()
    chunks = await search_chunks(
        query=req.question,
        collection_name=collection,
        top_k=req.top_k * 3,
    )
    if req.paper_ids:
        chunks = [c for c in chunks if c["paper_id"] in target_pids]
    chunks = chunks[:req.top_k * 5]
    embedding_ms = (time.monotonic() - t0) * 1000

    if not chunks:
        async def empty():
            yield "data: " + json.dumps({"type": "done", "answer": "抱歉，我在你的论文库中没有找到相关内容。"}) + "\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    # 构建 context
    from chat import build_context, evaluate_answer, SYSTEM_PROMPT_DEFAULT, SYSTEM_PROMPT_METHODOLOGY, SYSTEM_PROMPT_SURVEY
    if req.mode == "methodology":
        system_prompt = SYSTEM_PROMPT_METHODOLOGY
        context = build_context(chunks)
    elif req.mode == "survey":
        theme = req.question
        context_blocks = []
        for i, c in enumerate(chunks[:15]):
            context_blocks.append(f"[片段{i+1}] {c['content']}")
        context = "\n\n".join(context_blocks)
        system_prompt = SYSTEM_PROMPT_SURVEY.format(theme=theme)
    else:
        system_prompt = SYSTEM_PROMPT_DEFAULT
        context = build_context(chunks)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"问题：{req.question}\n\n{context}"},
    ]

    async def stream_generator():
        try:
            yield "data: " + json.dumps({"type": "start", "embedding_ms": round(embedding_ms)}) + "\n\n"
            client = MiniMaxChatClient(api_key=MINIMAX_API_KEY, group_id=MINIMAX_GROUP_ID)
            full_answer = ""
            for token in client.stream_chat(messages=messages, model=CHAT_MODEL, max_tokens=4096, temperature=0.3):
                full_answer += token
                yield "data: " + json.dumps({"type": "token", "content": token}) + "\n\n"
            # citations: 提取论文标题和页码（去重）
            cite_set = {}
            for c in chunks:
                pid = c["paper_id"]
                if pid not in cite_set:
                    cite_set[pid] = {
                        "title": c.get("title") or c.get("paper_id", "未知论文"),
                        "page": c.get("page_number", ""),
                    }
            citations = list(cite_set.values())
            # 自我评分 + 质量警告
            quality_warning = None
            try:
                self_eval = evaluate_answer(req.question, full_answer, chunks)
                score = self_eval.get("total", 100)
                if score < SCORE_THRESHOLD:
                    get_feedback_store().add_failed(
                        question=req.question,
                        answer=full_answer,
                        scores=self_eval,
                        chunks_count=len(chunks),
                        retrieval_strategy="default",
                    )
                    dim_str = " / ".join([
                        f"{k}={v}" for k, v in self_eval.items()
                        if k not in ("raw_evaluation", "json_mode") and v is not None
                    ])
                    quality_warning = f"⚠️ 质量 {score}/100（{dim_str}），已记录用于改进"
            except Exception as eval_err:
                print(f"[/chat/stream] 质量评估失败: {eval_err}")
            yield "data: " + json.dumps({
                "type": "done",
                "answer": full_answer,
                "citations": citations,
                "quality_warning": quality_warning,
            }) + "\n\n"
        except Exception as e:
            print(f"[/chat/stream] ❌ 流式生成失败: {e}")
            yield "data: " + json.dumps({"type": "error", "message": str(e)}) + "\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# ─── 反馈系统状态 ─────────────────────────────────────
@app.get("/feedback/stats")
async def feedback_stats():
    """查看差评反馈系统统计"""
    store = get_feedback_store()
    stats = store.stats()
    return {
        "threshold": SCORE_THRESHOLD,
        **stats,
    }


@app.get("/quality/report")
async def quality_report(user_info: tuple = Depends(get_current_user)):
    """
    质量仪表盘 — 返回完整的质量分析报告
    用于持续追踪答案质量、失败原因分布、评分解析成功率
    """
    store = get_feedback_store()
    return store.quality_report()


@app.delete("/feedback/entries/{entry_id}")
async def delete_feedback_entry(entry_id: str, user_info: tuple = Depends(get_current_user)):
    """删除某条差评记录（用于清理误报）"""
    store = get_feedback_store()
    db = store._load()
    original = len(db["entries"])
    db["entries"] = [e for e in db["entries"] if e["id"] != entry_id]
    store._save(db)
    deleted = original - len(db["entries"])
    if deleted == 0:
        raise HTTPException(404, "未找到该记录")
    return {"deleted": deleted}


@app.get("/me/quota")
async def my_quota(user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    # papers_used 只统计状态为 ready 的论文（索引成功才计入配额）
    ready_count = sum(
        1 for pid in user["papers"]
        if get_paper(pid) and get_paper(pid).get("status") == "ready"
    )
    return {
        "plan": user["plan"],
        "papers_used": ready_count,
        "papers_limit": None if user["plan"] == "pro" else 20,
        "collection": _col(user["user_id"]),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
