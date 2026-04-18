"""
Router: 认证 — /auth/register, /auth/login
Phase 0.8: 手机号 + 密码登录（无短信验证）
"""
import uuid
from fastapi import APIRouter, HTTPException, Depends, Header, Cookie, Response
from pydantic import BaseModel

from auth import create_access_token, verify_token, hash_password, verify_password
from state import users_db, users_by_email, users_by_phone, get_users_db
from data import save_users, assign_default_folder
from folders_db import create as create_folder
from config import PAPERS_DIR
from rate_limit import check_login_rate_limit, _record_failure, clear_login_failures

COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds

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

def get_current_user(
    authorization: str = Header(None, alias="Authorization"),
    rag_token: str = Cookie(None, alias="rag_token"),
):
    """依赖注入：从 Authorization header 或 rag_token Cookie 解析当前登录用户

    支持两种认证方式：
    1. Authorization: Bearer <token>  (标准 Header)
    2. Cookie: rag_token=<token>      (WebView/嵌入式浏览器兼容)
    """
    # 优先使用 Authorization header，其次使用 Cookie
    token = None
    if authorization:
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise HTTPException(401, "无效的认证方式")
        except ValueError:
            raise HTTPException(401, "无效的 Authorization 格式")
    elif rag_token:
        token = rag_token
    else:
        raise HTTPException(401, "未提供认证信息")

    try:
        payload = verify_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(401, "Token 无用户ID")
        db = get_users_db()
        if user_id not in db:
            raise HTTPException(401, "用户不存在")
        return user_id, db[user_id]
    except HTTPException:
        raise
    except Exception:
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
async def login(req: LoginRequest, response: Response):
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

    # 设置 HttpOnly Cookie（WebView 环境比 localStorage 更稳定）
    response.set_cookie(
        key="rag_token",
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # 生产环境设为 True 并启用 HTTPS
        path="/",
    )

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
