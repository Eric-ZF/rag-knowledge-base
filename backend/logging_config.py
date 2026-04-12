"""
统一日志配置 — 全部使用 logging 模块，禁用所有 print()
"""
import logging
import sys

def setup_logging():
    """在 uvicorn 启动前调用一次，全局生效"""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # 避免重复添加 handler
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
