"""
Router: 反馈与质量 — /feedback, /quality, /me/quota
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from feedback import get_feedback_store, SCORE_THRESHOLD
from state import users_db, get_users_db
from routers.auth import get_current_user

router = APIRouter(tags=["feedback"])

class QuotaResponse(BaseModel):
    used: int
    limit: int
    plan: str

class EntryDeleteResponse(BaseModel):
    ok: bool

class EntryResponse(BaseModel):
    id: str
    question: str
    scores: dict
    failure_reasons: list[str]
    timestamp: str

@router.get("/feedback/stats")
async def feedback_stats():
    store = get_feedback_store()
    stats = store.stats()
    return {"threshold": SCORE_THRESHOLD, **stats}

@router.get("/quality/report")
async def quality_report():
    store = get_feedback_store()
    return store.quality_report()

@router.delete("/feedback/entries/{entry_id}", response_model=EntryDeleteResponse)
async def delete_feedback_entry(entry_id: str, user_info: tuple = Depends(get_current_user)):
    store = get_feedback_store()
    store.delete_entry(entry_id)
    return {"ok": True}

@router.get("/me/quota", response_model=QuotaResponse)
async def my_quota(user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    plan = user.get("plan", "free")
    limit = 999 if plan == "pro" else 20
    return {
        "used": len(user.get("papers", [])),
        "limit": limit,
        "plan": plan,
    }
