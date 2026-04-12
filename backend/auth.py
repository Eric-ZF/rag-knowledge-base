"""
Phase 0.7：JWT 认证工具
- HS256 + bcrypt 密码哈希
- JWT Secret 从环境变量读取（Phase 1 必须配置）
"""

import os
from datetime import datetime, timedelta
from typing import Any

from jose import jwt, JWTError
import bcrypt
from dotenv import load_dotenv
load_dotenv()

# JWT Secret — 必须从环境变量读取，不允许使用默认 fallback
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError(
        "❌ JWT_SECRET 环境变量未设置。"
        "请在 backend/.env 中添加: JWT_SECRET=<随机字符串>"
        "生成方式: python3 -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )
if len(SECRET_KEY) < 32:
    raise RuntimeError("❌ JWT_SECRET 长度至少需要 32 字符（建议 64 字符）")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 小时


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Token 无效: {e}")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False
