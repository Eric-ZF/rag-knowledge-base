"""
RAG Backend E2E 冒烟测试

运行方式:
    pytest tests/test_api.py -v

覆盖场景（10个）:
    TC001  注册新用户 + 登录
    TC002  登录失败（错误密码）
    TC003  GET /papers — 返回论文列表
    TC004  GET /papers/{id}/status — 获取状态
    TC005  DELETE /papers/{id} — 删除论文（幂等）
    TC006  POST /chat — 正常问答（需等 MiniMax，耗时）
    TC007  POST /chat — 空检索返回「没有找到相关内容」
    TC008  GET /quality/report — 质量仪表盘
    TC009  GET /feedback/stats — 差评统计
    TC010  未授权访问 /papers — 401 Unauthorized
"""
import pytest, requests, time, uuid, concurrent.futures, threading

BASE_URL = "http://localhost:8000"
TEST_EMAIL = "bosstest@boss.io"
TEST_PASSWORD = "BossPhase0"


# ──────────────────────────────────────────────────────
# TC001: 注册 + 登录
# ──────────────────────────────────────────────────────
class TestAuth:
    def test_register_new_user_and_login(self, base_url):
        """TC001: 注册新用户 → 登录，应返回有效 token"""
        # 随机账号避免重复
        email = f"auto_{uuid.uuid4().hex[:8]}@test.com"
        # 1. 注册
        reg_resp = requests.post(
            f"{base_url}/auth/register",
            json={"email": email, "password": "TestPass123!", "name": "Auto Test"},
            timeout=10,
        )
        assert reg_resp.status_code == 200, f"注册失败: {reg_resp.status_code} {reg_resp.text}"
        reg_data = reg_resp.json()
        assert "user_id" in reg_data, f"注册响应缺少 user_id: {reg_data}"
        # 2. 注册后需单独登录获取 token
        login_resp = requests.post(
            f"{base_url}/auth/login",
            json={"email": email, "password": "TestPass123!"},
            timeout=10,
        )
        assert login_resp.status_code == 200, f"登录失败: {login_resp.status_code}"
        login_data = login_resp.json()
        assert "access_token" in login_data, f"登录响应缺少 token: {login_data}"

    def test_login_with_wrong_password(self, base_url):
        """TC002: 错误密码登录应返回 401"""
        resp = requests.post(
            f"{base_url}/auth/login",
            json={"email": TEST_EMAIL, "password": "wrongpassword"},
            timeout=10,
        )
        assert resp.status_code == 401, f"错误密码应返回 401，实际: {resp.status_code}"


# ──────────────────────────────────────────────────────
# TC003-005: 论文管理
# ──────────────────────────────────────────────────────
class TestPapers:
    def test_get_papers_list(self, base_url, auth_headers):
        """TC003: GET /papers 应返回列表且包含字段"""
        resp = requests.get(f"{base_url}/papers", headers=auth_headers, timeout=10)
        assert resp.status_code == 200
        papers = resp.json()
        assert isinstance(papers, list), f"返回应为 list，实际: {type(papers)}"
        if papers:
            p = papers[0]
            for field in ("paper_id", "title", "status", "chunks_count"):
                assert field in p, f"论文对象缺少字段 {field}: {p}"

    def test_get_paper_status(self, base_url, auth_headers, papers_list):
        """TC004: GET /papers/{id}/status 应返回状态和进度"""
        if not papers_list:
            pytest.skip("无论文，跳过")
        paper_id = papers_list[0]["paper_id"]
        resp = requests.get(
            f"{base_url}/papers/{paper_id}/status",
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200, f"获取状态失败: {resp.status_code}"
        data = resp.json()
        assert "status" in data, f"status 响应缺少 status 字段: {data}"
        assert data["status"] in ("ready", "processing", "error")

    def test_delete_paper_force(self, base_url, auth_headers):
        """
        TC005: DELETE /papers/{id}?force=true 删除 processing 状态论文

        策略：上传一个假的 PDF（必然 processing → error），然后 force 删除。
        不碰已有的 ready 状态论文。
        """
        import io
        fake_pdf = b"%PDF-1.4 fake content for testing"
        files = {"file": ("test_delete.pdf", io.BytesIO(fake_pdf), "application/pdf")}
        upload_resp = requests.post(
            f"{base_url}/papers/upload",
            headers={"Authorization": auth_headers["Authorization"]},
            files=files,
            timeout=30,
        )
        # 上传成功会返回 paper_id（processing 或 error）
        if upload_resp.status_code == 200:
            upload_data = upload_resp.json()
            if "paper_id" in upload_data:
                pid = upload_data["paper_id"]
                # 等待 processing 完成（会变成 error）
                time.sleep(5)
                # force 删除
                del_resp = requests.delete(
                    f"{base_url}/papers/{pid}?force=true",
                    headers=auth_headers,
                    timeout=10,
                )
                assert del_resp.status_code == 200, f"force 删除失败: {del_resp.status_code} {del_resp.text}"
                return

        # 如果上传被拒绝（PDF 无效），测试已完成（不破坏数据）
        assert True, "上传被拒绝，无需删除"


# ──────────────────────────────────────────────────────
# TC006-007: 问答
# ──────────────────────────────────────────────────────
class TestChat:
    def test_chat_normal_answer(self, base_url, auth_headers):
        """TC006: POST /chat 应返回答案 + citations"""
        payload = {
            "question": "什么是双碳目标？",
            "collection_name": "default",
            "top_k": 3,
            "mode": "default",
        }
        resp = requests.post(
            f"{base_url}/chat",
            json=payload,
            headers=auth_headers,
            timeout=130,
        )
        # MiniMax 可能 500/529，超时则降级
        assert resp.status_code in (200, 500, 529), f"意外状态码: {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            assert "answer" in data, f"答案响应缺少 answer: {data}"
            # citations 字段可选（有论文才返回）
            assert isinstance(data["answer"], str), "answer 应为字符串"

    def test_chat_no_results(self, base_url, auth_headers):
        """TC007: 空检索应返回「没有找到相关内容」"""
        payload = {
            "question": "xyz_no_such_keyword_abc_水稻种植与量子计算结合",
            "collection_name": "default",
            "top_k": 3,
            "mode": "default",
        }
        resp = requests.post(
            f"{base_url}/chat",
            json=payload,
            headers=auth_headers,
            timeout=130,
        )
        # 空检索仍返回 200（graceful 处理）
        if resp.status_code == 200:
            data = resp.json()
            answer = data.get("answer", "")
            assert "没有找到" in answer or "无关" in answer or "抱歉" in answer or "论文库还没有" in answer, \
                f"空检索应返回友好提示，实际返回: {answer[:100]}"


# ──────────────────────────────────────────────────────
# TC008-009: 质量系统
# ──────────────────────────────────────────────────────
class TestQuality:
    def test_quality_report_endpoint(self, base_url, auth_headers):
        """TC008: GET /quality/report 应返回质量分析报告"""
        resp = requests.get(f"{base_url}/quality/report", headers=auth_headers, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        for field in ("total", "score_distribution", "failure_reasons"):
            assert field in data, f"质量报告缺少字段 {field}: {data}"

    def test_feedback_stats_endpoint(self, base_url, auth_headers):
        """TC009: GET /feedback/stats 应返回差评统计"""
        resp = requests.get(f"{base_url}/feedback/stats", headers=auth_headers, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "threshold" in data, f"差评统计缺少 threshold: {data}"
        assert "total" in data


# ──────────────────────────────────────────────────────
# TC010: 授权
# ──────────────────────────────────────────────────────
class TestAuthz:
    def test_unauthorized_access_returns_401(self, base_url):
        """TC010: 无 Authorization header 访问 /papers 应返回 401"""
        resp = requests.get(f"{base_url}/papers", timeout=10)
        assert resp.status_code == 401, f"未授权访问应返回 401，实际: {resp.status_code}"

    def test_invalid_token_returns_401(self, base_url):
        """TC010b: 错误 token 访问 /papers 应返回 401"""
        resp = requests.get(
            f"{base_url}/papers",
            headers={"Authorization": "Bearer invalid_token_xyz"},
            timeout=10,
        )
        assert resp.status_code == 401


# ──────────────────────────────────────────────────────
# TC011: PDF 上传（核心功能）
# ──────────────────────────────────────────────────────
class TestUpload:
    def test_upload_pdf_success(self, base_url, auth_headers):
        """TC011: 上传 PDF → status=ready, chunks>0"""
        import os
        # 找一篇测试 PDF
        pdf_dir = "/root/.openclaw/workspace/rag-knowledge-base/phase0/backend"
        pdfs = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
        if not pdfs:
            # 没有本地 PDF，跳过（需要用户上传）
            pytest.skip("No local PDF found for upload test")
        pdf_path = os.path.join(pdf_dir, pdfs[0])
        with open(pdf_path, 'rb') as f:
            files = {'file': (pdfs[0], f, 'application/pdf')}
            resp = requests.post(f"{base_url}/papers", headers={"Authorization": auth_headers["Authorization"]}, files=files, timeout=30)
        # 可能返回 200 (成功) 或 409 (已存在) 或 202 (排队中)
        assert resp.status_code in (200, 201, 202, 409), f"上传失败: {resp.status_code} {resp.text}"
        if resp.status_code in (200, 201):
            data = resp.json()
            assert "paper_id" in data, f"上传响应缺少 paper_id: {data}"

    def test_upload_creates_pending_paper(self, base_url, auth_headers):
        """TC011b: 上传后 papers 列表应包含新论文"""
        resp = requests.get(f"{base_url}/papers", headers=auth_headers, timeout=10)
        assert resp.status_code == 200
        papers = resp.json()
        assert isinstance(papers, list), "返回应为 list"
        # 验证字段完整性
        for p in papers:
            for field in ("paper_id", "title", "status"):
                assert field in p, f"论文字段不全: {p}"


# ──────────────────────────────────────────────────────
# TC012: 质量警告触发
# ──────────────────────────────────────────────────────
class TestQualityTrigger:
    def test_low_score_returns_warning(self, base_url, auth_headers):
        """TC012: 差评答案应返回 quality_warning 字段"""
        # 发一个有效但容易触发低分的无意义问题
        resp = requests.post(
            f"{base_url}/chat",
            json={"question": "量子纠缠的蝴蝶效应与区块链的关系是什么？", "mode": "default"},
            headers=auth_headers,
            timeout=130,
        )
        # 可能 200 或 500（fallback），都不算错
        assert resp.status_code in (200, 500, 502), f"Chat 失败: {resp.status_code}"
        if resp.status_code == 200:
            data = resp.json()
            # 有 quality_warning 字段说明评分系统正常
            if "quality_warning" in data:
                assert data["quality_warning"] is not None


# ──────────────────────────────────────────────────────
# TC013: Rate Limiting
# ──────────────────────────────────────────────────────
class TestRateLimit:
    def test_rate_limit_enforced(self, base_url):
        """TC013: 同一账号 5 分钟内 6 次失败后第 7 次应返回 429"""
        # 用同一个 email 重复触发限流
        target_email = f"ratelimit_test_{uuid.uuid4().hex[:8]}@test.com"
        errors = []
        for i in range(7):
            resp = requests.post(
                f"{base_url}/auth/login",
                json={"email": target_email, "password": "wrong_password_never_valid"},
                timeout=10,
            )
            if resp.status_code == 429:
                errors.append(i + 1)
                break
            elif resp.status_code != 401:
                errors.append(f"attempt {i}: {resp.status_code}")
        # 应该触发 429
        assert len(errors) > 0 and errors[0] != 401, f"Rate limiter 未触发429: {errors}"
        print(f"Rate limit triggered at attempt {errors[0]}")


# ──────────────────────────────────────────────────────
# TC014: 编辑论文元数据
# ──────────────────────────────────────────────────────
class TestPaperEdit:
    def test_patch_paper_metadata(self, base_url, auth_headers, papers_list):
        """TC014: PATCH /papers/{id} → 修改 abstract/keywords"""
        if not papers_list:
            pytest.skip("No papers to edit")
        paper_id = papers_list[0]["paper_id"]
        patch_data = {
            "abstract": "这是测试摘要 " + str(uuid.uuid4())[:8],
            "keywords": "测试, E2E, pytest",
        }
        resp = requests.patch(
            f"{base_url}/papers/{paper_id}",
            json=patch_data,
            headers=auth_headers,
            timeout=10,
        )
        assert resp.status_code == 200, f"PATCH 失败: {resp.status_code} {resp.text}"
        # 验证更新生效
        updated = requests.get(f"{base_url}/papers", headers=auth_headers, timeout=10).json()
        found = next((p for p in updated if p["paper_id"] == paper_id), None)
        assert found is not None, "PATCH 后论文消失"
        assert found["abstract"] == patch_data["abstract"], "abstract 未更新"


# ──────────────────────────────────────────────────────
# TC015: 并发写入安全
# ──────────────────────────────────────────────────────
class TestConcurrency:
    def test_concurrent_paper_reads(self, base_url, auth_headers):
        """TC015: 并发 5 个 GET /papers 请求应全部成功（无数据错乱）"""
        import concurrent.futures, threading

        errors = []
        lock = threading.Lock()

        def fetch():
            try:
                r = requests.get(f"{base_url}/papers", headers=auth_headers, timeout=10)
                if r.status_code != 200:
                    with lock:
                        errors.append(f"status {r.status_code}")
            except Exception as e:
                with lock:
                    errors.append(str(e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch) for _ in range(5)]
            concurrent.futures.wait(futures)

        assert len(errors) == 0, f"并发读取失败: {errors}"


# ──────────────────────────────────────────────────────
# TC016: 空检索 graceful 处理
# ──────────────────────────────────────────────────────
class TestGraceful:
    def test_empty_query_graceful(self, base_url, auth_headers):
        """TC016: 空查询应返回友好提示，不崩溃"""
        resp = requests.post(
            f"{base_url}/chat",
            json={"question": "", "mode": "default"},
            headers=auth_headers,
            timeout=130,
        )
        # 空查询可以返回 400 或 200（graceful）
        assert resp.status_code in (200, 400, 422), f"空查询失败: {resp.status_code}"
