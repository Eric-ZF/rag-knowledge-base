"""
RAG Backend E2E 测试 — pytest 配置

所有测试共享:
- BASE_URL: http://localhost:8000
- 固定测试用户账号 (bosstest@boss.io / BossPhase0)
- 自动获取/刷新 token fixture
"""
import pytest, requests

BASE_URL = "http://localhost:8000"
TEST_PHONE = "13800138000"
TEST_PASSWORD = "BossPhase0"


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def auth_token(base_url) -> str:
    """获取有效 token（session 级，所有测试复用）"""
    resp = requests.post(
        f"{base_url}/auth/login",
        json={"phone": TEST_PHONE, "password": TEST_PASSWORD},
        timeout=10,
    )
    assert resp.status_code == 200, f"登录失败: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "access_token" in data, f"登录响应缺少 token: {data}"
    return data["access_token"]


@pytest.fixture
def auth_headers(auth_token) -> dict:
    """带 Authorization 的请求头"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture
def papers_list(base_url, auth_headers) -> list:
    """当前论文列表"""
    resp = requests.get(f"{base_url}/papers", headers=auth_headers, timeout=10)
    assert resp.status_code == 200
    return resp.json()
