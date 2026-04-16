"""
Router: 认证 — /auth/register, /auth/login
Phase 0.8: 手机号 + 密码登录（无短信验证）
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

from auth import create_access_token, verify_token, hash_password, verify_password
from state import users_db, users_by_email, users_by_phone, get_users_db
from data import save_users, assign_default_folder
from folders_db import create as create_folder
from config import PAPERS_DIR
from rate_limit import check_login_rate_limit, _record_failure, clear_login_failures

router = APIRouter(prefix="/auth", tags=["auth"])

def _col(user_id: str) -> str:
    return f"user_{user_id.replace('-', '_')}"

class RegisterRequest(BaseModel):
    phone: str
    password: str

class LoginRequest(BaseModel):
    phone: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    plan: str

class RegisterResponse(BaseModel):
    user_id: str
    phone: str

class SetPasswordRequest(BaseModel):
    password: str

def get_current_user(authorization: str = Header(None)):
    """依赖注入：从 Authorization header 解析当前登录用户"""
    if not authorization:
        raise HTTPException(401, "未提供认证信息")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(401, "无效的认证方式")
        payload = verify_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(401, "Token 无用户ID")
        db = get_users_db()
        if user_id not in db:
            raise HTTPException(401, "用户不存在")
        return user_id, db[user_id]
    except (ValueError, KeyError):
        raise HTTPException(401, "无效的 Token")


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest):
    phone, password = req.phone.strip(), req.password
    if len(password) < 6:
        raise HTTPException(400, "密码至少需要 6 位")
    if phone in users_by_phone:
        raise HTTPException(400, "该手机号已注册，请直接登录")

    user_id = str(uuid.uuid4())
    folder_id = str(uuid.uuid4())
    user_record = {
        "user_id": user_id,
        "phone": phone,
        "password": hash_password(password),
        "plan": "free",
        "default_folder_id": folder_id,
        "created_at": "",
    }
    users_db[user_id] = user_record
    users_by_phone[phone] = user_record
    save_users()

    # 为新用户创建默认文件夹
    create_folder(folder_id, user_id, "我的文献", parent_id=None)

    return {"user_id": user_id, "phone": phone}


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    check_login_rate_limit(req.phone)
    phone, password = req.phone.strip(), req.password
    user = users_by_phone.get(phone)
    if not user:
        _record_failure(req.phone)
        raise HTTPException(401, "手机号或密码错误")
    if not verify_password(password, user["password"]):
        _record_failure(req.phone)
        raise HTTPException(401, "手机号或密码错误")

    clear_login_failures(req.phone)
    token = create_access_token({"sub": user["phone"], "user_id": user["user_id"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "plan": user.get("plan", "free"),
    }


@router.post("/set-password")
async def set_password(req: SetPasswordRequest, user_info: tuple = Depends(get_current_user)):
    """为已有账号（old-bosstest）设置密码"""
    user_id, user = user_info
    if len(req.password) < 6:
        raise HTTPException(400, "密码至少需要 6 位")
    if user.get("password"):
        raise HTTPException(400, "已设置过密码，请使用密码登录")
    user["password"] = hash_password(req.password)
    save_users()
    return {"ok": True}
