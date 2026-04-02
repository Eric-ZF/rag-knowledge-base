"""Phase 1 — 论文管理 API"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from ..storage import papers as p

router = APIRouter()


@router.get("/papers")
async def list_papers(limit: int = Query(100, ge=1, le=500)):
    """列出所有文献"""
    return p.get_all_papers(limit=limit)


@router.get("/papers/{paper_id}")
async def get_paper(paper_id: str):
    paper = p.get_paper(paper_id)
    if not paper:
        raise HTTPException(404, "文献不存在")
    return paper


@router.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str):
    from ..retrieval import delete_paper_vectors
    delete_paper_vectors(paper_id)
    p.delete_paper(paper_id)
    return {"ok": True, "paper_id": paper_id}


@router.get("/papers/{paper_id}/sections")
async def get_sections(paper_id: str):
    return p.get_sections_by_paper(paper_id)


@router.get("/papers/{paper_id}/chunks")
async def get_paper_chunks(
    paper_id: str,
    level: Optional[str] = Query(None, description="recall 或 evidence"),
):
    return p.get_chunks_by_paper(paper_id, chunk_level=level)


@router.get("/papers/{paper_id}/profile")
async def get_paper_profile(paper_id: str):
    profile = p.get_profile(paper_id)
    if not profile:
        raise HTTPException(404, "文献画像不存在")
    return profile


@router.get("/chunks/{chunk_id}")
async def get_chunk(chunk_id: str):
    chunk = p.get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(404, "Chunk 不存在")
    return chunk


@router.get("/qa-logs")
async def list_qa_logs(limit: int = Query(50, ge=1, le=200)):
    return p.get_recent_qa_logs(limit=limit)
