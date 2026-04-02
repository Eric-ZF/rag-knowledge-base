"""Phase 1 — 上传 API"""
import asyncio, json
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from ..ingestion import ParserFactory, ParsedDocument
from ..chunking import chunk_document
from ..storage import papers as p
from ..retrieval import upsert_chunks
from ..pipeline import encode_texts

router = APIRouter()

# ─── SSE 进度事件 ─────────────────────────────────────

processing_events: dict[str, dict] = {}


def emit(paper_id: str, stage: str, progress: float, message: str = "", chunks_count: int | None = None):
    processing_events[paper_id] = {
        "stage": stage,
        "progress": progress,
        "message": message,
        "chunks_count": chunks_count,
    }


async def ingest_document(paper_id: str, file_bytes: bytes, filename: str):
    """完整 ingestion 流水线（异步，BackgroundTasks）"""
    try:
        # Stage 1: 解析
        emit(paper_id, "parsing", 0.1, "正在解析文档...")
        parsed: ParsedDocument = ParserFactory.parse(file_bytes, filename)
        emit(paper_id, "parsed", 0.3, f"解析完成：{len(parsed.sections)} 个章节")

        # Stage 2: 章节入库
        emit(paper_id, "chunking", 0.4, "正在进行两级 chunk 切分...")
        sections_data = [
            {
                "section_id": None,  # 后续填充
                "title": s.title,
                "path": s.path,
                "order": s.order,
                "page_start": s.page_start,
                "page_end": s.page_end,
                "paragraphs": s.paragraphs,
            }
            for s in parsed.sections
        ]

        # 先创建 paper 记录
        paper = p.create_paper(
            title=parsed.title or filename,
            file_bytes=file_bytes,
            file_name=filename,
            authors=parsed.authors,
            year=parsed.year,
            language=parsed.language,
            abstract=parsed.abstract,
            keywords=parsed.keywords,
        )
        paper_id_stored = paper["paper_id"]

        # 创建 sections
        section_id_map = {}
        for s in parsed.sections:
            sid = p.create_section(
                paper_id=paper_id_stored,
                title=s.title,
                path=s.path,
                section_order=s.order,
                page_start=s.page_start,
                page_end=s.page_end,
                text="\n".join(s.paragraphs),
            )
            section_id_map[s.order] = sid

        # 更新 sections_data 的 section_id
        for s_data in sections_data:
            s_data["section_id"] = section_id_map.get(s_data["order"])

        # 两级 chunk
        recall_chunks, evidence_chunks = chunk_document(paper_id_stored, sections_data)

        emit(paper_id, "embedding", 0.6, f"召回块 {len(recall_chunks)} 个，证据块 {len(evidence_chunks)} 个...")

        # Stage 3: 生成 embedding 并入库
        recall_texts = [rc.chunk_text for rc in recall_chunks]
        evidence_texts = [ec.chunk_text for ec in evidence_chunks]
        all_texts = recall_texts + evidence_texts

        # 批量 encode
        all_embeddings = encode_texts(all_texts)

        recall_embeddings = all_embeddings[: len(recall_texts)]
        evidence_embeddings = all_embeddings[len(recall_texts):]

        # 入库 recall chunks
        recall_db_ids = []
        for rc, emb in zip(recall_chunks, recall_embeddings):
            sid = section_id_map.get(rc.order // 100 if rc.order else 0)
            cid = p.create_chunk(
                paper_id=paper_id_stored,
                chunk_text=rc.chunk_text,
                chunk_level="recall",
                chunk_type="body",
                section_id=sid,
                token_count=rc.token_count,
                page_range=rc.page_range,
            )
            recall_db_ids.append((cid, rc.chunk_id))

        # 入库 evidence chunks
        chroma_chunks = []
        for ec, emb in zip(evidence_chunks, evidence_embeddings):
            # 找到对应的 recall_chunk_id
            recall_id = next(
                (rid for rid, rc_id in recall_db_ids if rc_id == f"{paper_id_stored}-rc-{ec.chunk_id[-7:-5]}" or True),
                recall_db_ids[0][0] if recall_db_ids else None,
            )
            cid = p.create_chunk(
                paper_id=paper_id_stored,
                chunk_text=ec.chunk_text,
                chunk_level="evidence",
                chunk_type=ec.chunk_type,
                recall_chunk_id=recall_id,
                section_id=ec.section_id,
                token_count=ec.token_count,
                page_range=ec.page_range,
            )
            chroma_chunks.append({
                "chunk_id": cid,
                "paper_id": paper_id_stored,
                "chunk_text": ec.chunk_text,
                "embedding": emb.tolist(),
                "metadata": {
                    "paper_id": paper_id_stored,
                    "chunk_type": ec.chunk_type,
                    "chunk_level": "evidence",
                    "page_range": ec.page_range,
                },
            })

        emit(paper_id, "indexing", 0.8, f"写入向量库 {len(chroma_chunks)} 个证据块...")
        upsert_chunks(chroma_chunks)

        emit(paper_id, "complete", 1.0, "索引完成", chunks_count=len(chroma_chunks))

    except Exception as e:
        emit(paper_id, "error", 0, str(e))
        raise


@router.post("/upload")
async def upload(
    background: BackgroundTasks,
    file: UploadFile = File(...),
):
    """上传 PDF，返回 paper_id 和 SSE 进度流"""
    if not file.filename:
        raise HTTPException(400, "未提供文件名")

    import uuid
    paper_id = f"upload-{uuid.uuid4().hex[:12]}"

    file_bytes = await file.read()

    # 检查重复
    import hashlib
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    dup = p.check_duplicate_hash(file_hash)
    if dup:
        raise HTTPException(409, {
            "error": "duplicate_file",
            "message": f"该文件已上传，paper_id: {dup['paper_id']}",
            "title": dup["title"],
            "version": dup["version"],
        })

    processing_events[paper_id] = {"stage": "queued", "progress": 0.0, "message": "排队中", "chunks_count": None}

    background.add_task(ingest_document, paper_id, file_bytes, file.filename)

    async def event_stream():
        import asyncio
        last_state = None
        while True:
            event = processing_events.get(paper_id)
            if event and event != last_state:
                yield f"data: {json.dumps(event)}\n\n"
                last_state = event
                if event["stage"] in ("complete", "error"):
                    break
            await asyncio.sleep(0.5)
        yield f"data: {json.dumps({'stage': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/upload/{paper_id}/status")
async def upload_status(paper_id: str):
    event = processing_events.get(paper_id, {})
    return {
        "paper_id": paper_id,
        **event,
    }
