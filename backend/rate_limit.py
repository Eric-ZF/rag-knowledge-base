"""
简单内存限流：记录每个邮箱的登录失败次数
超过阈值后返回 429，直到窗口过期
"""
import time
import threading
from collections import defaultdict
from typing import Callable

# ─── 配置 ────────────────────────────────────────────
MAX_LOGIN_ATTEMPTS = 5       # 窗口内最多失败次数
LOGIN_WINDOW_SECONDS = 300     # 5 分钟窗口
RATE_LIMIT_ENABLED = True     # 上线后确认稳定可关闭

# ─── 内存存储 ─────────────────────────────────────────
_login_failures: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()

def _record_failure(key: str) -> None:
    """记录一次登录失败"""
    if not RATE_LIMIT_ENABLED:
        return
    with _lock:
        now = time.time()
        # 清理过期记录
        _login_failures[key] = [
            t for t in _login_failures[key]
            if now - t < LOGIN_WINDOW_SECONDS
        ]
        _login_failures[key].append(now)

def check_login_rate_limit(key: str) -> bool:
    """
    检查是否被限流。返回 True = 被限流（应拒绝），
    False = 正常（可以继续）。
    """
    if not RATE_LIMIT_ENABLED:
        return False
    with _lock:
        now = time.time()
        recent = [t for t in _login_failures[key] if now - t < LOGIN_WINDOW_SECONDS]
        return len(recent) >= MAX_LOGIN_ATTEMPTS

def clear_login_failures(key: str) -> None:
    """登录成功后清除失败记录"""
    if not RATE_LIMIT_ENABLED:
        return
    with _lock:
        _login_failures.pop(key, None)
