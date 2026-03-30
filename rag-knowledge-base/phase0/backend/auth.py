"""
Phase 0：JWT 认证工具

⚠️ Phase 0 使用 HS256 简化实现（开发/验证速度快）
⚠️ 生产环境（Phase 1+）必须切换为 RS256，防止密钥泄露导致完全伪造 Token
"""

import os
from datetime import datetime, timedelta
from typing import Any

from jose import jwt, JWTError

# Phase 0：使用 HS256 + 简单密钥
# 生产环境要换成 RS256：openssl genrsa -out private.pem 2048
SECRET_KEY = os.getenv("JWT_SECRET", "phase0-dev-secret-change-in-production")
ALGORITHM = "HS256"  # ⚠️ Phase 1+ 换成 RS256
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """生成 JWT Token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """验证并解码 JWT Token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Token 无效: {e}")


# ─── Password Hashing（Phase 0 简化）───────────────────
# 生产环境使用 bcrypt（requirements.txt 已含）
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
