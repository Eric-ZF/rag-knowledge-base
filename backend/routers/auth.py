"""
Router: 认证 — /auth/register, /auth/login
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from auth import create_access_token, verify_token, hash_password, verify_password
from state import users_db, users_by_email, get_users_db
from data import save_users
from config import PAPERS_DIR

router = APIRouter(prefix="/auth", tags=["auth"])

def _col(user_id: str) -> str:
    return f"user_{user_id.replace('-', '_')}"

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    collection: str
    plan: str

class RegisterResponse(BaseModel):
    user_id: str
    collection: str


def get_current_user(authorization: str = Header(None)):
    """依赖注入：从 Authorization header 解析当前登录用户"""
    if not authorization:
        raise HTTPException(401, "未提供认证信息")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(401, "无效的认证方式")
        payload = verify_token(token)
        email = payload["sub"]
        user_id = payload.get("user_id")
        db = get_users_db()
        if not user_id or user_id not in db:
            raise HTTPException(401, "用户不存在")
        return user_id, db[user_id]
    except (ValueError, KeyError):
        raise HTTPException(401, "无效的 Token")


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest):
    email, password = req.email, req.password
    if email in users_by_email:
        raise HTTPException(400, "邮箱已注册")
    user_id = str(uuid.uuid4())
    collection_name = _col(user_id)
    user_record = {
        "email": email,
        "user_id": user_id,
        "password": hash_password(password),
        "plan": "free",
        "papers": [],
        "collection": _col(user_id),
    }
    users_db[user_id] = user_record
    users_by_email[email] = user_record
    save_users()
    return {"user_id": user_id, "collection": collection_name}


@router.post("/login", response_model=TokenResponse)
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
