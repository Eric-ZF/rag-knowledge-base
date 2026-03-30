# RAG 学术知识库 — 测试策略

> 生成时间：2026-03-30 17:58 GMT+8
> 更新时间：2026-03-30 20:52 GMT+8（v3.0 — 深度优化版）
> 模式：gstack:qa (Google SET + James Whittaker 测试架构思维)
> 依据：CEO-analysis.md (v2.0) · ENG-architecture.md (v2.1) · DESIGN-interaction.md (v4.1)

---

## 0. 优化日志

| 版本 | 更新内容 |
|-----|---------|
| v1.0 (17:58) | 初始测试策略 — 测试金字塔、单元/集成/E2E、RAG 质量评估体系、性能测试、CI/CD 流水线 |
| v2.0 (18:02) | 混沌/韧性测试、JWT 安全专项、Flaky 处理规范、金丝雀 E2E、PDF 解析质量量化、向量检索指标(Recall@K/MRR@K)、测试分层执行、安全测试专项、生产质量监控 |
| **v3.0 (20:52)** | **Bug 分类体系、PostgreSQL RLS 测试、数据库迁移测试、Feature Flag 测试、API 版本兼容性、i18n 测试、Golden Dataset 管理规范、搜索排序回归、限流算法正确性、Staging 数据真实性、快速冒烟子集、LangChain 组件测试** |

---

## 1. Bug 分类体系（新增）

> 没有精确定义的 Bug 分类导致团队争执和优先级错位。每一个 Bug 必须有明确的严重级别定义。

### 1.1 四级 Bug 定义

| 级别 | 定义 | 例子 | SLA | 发布阻断 |
|-----|------|------|-----|---------|
| **P0** | **数据泄露 / 系统不可用** 任何导致用户数据暴露或系统完全无法服务的缺陷 | 跨用户检索泄露、认证绕过、索引pipeline崩溃、论文原文件泄露 | 4h 内必须有人在处理 | ✅ 阻塞发布 |
| **P1** | **核心功能受损** 主要流程无法完成，影响大量用户 | 论文上传后永久无法索引、RAG 问答返回空答案、搜索100%返回错误、批量删除失败 | 24h 内 fix 或找到 workaround | ✅ 阻塞发布 |
| **P2** | **功能缺陷** 功能不正常但有 workaround，或者非核心路径失败 | 收藏夹排序丢失、DOCX 导出格式错乱、非核心页面样式异常 | 72h 内 fix | ❌ 不阻塞，但需记录 |
| **P3** | **体验问题** 视觉、文案、边缘交互，不影响功能 | 按钮圆角差 1px、Toast 位置偏移 2px、loading 动画不够流畅 | 1 周内 fix | ❌ 不阻塞 |

### 1.2 Bug 分类决策树

```
发现 Bug
  │
  ├─ 数据是否泄露？ ── → P0
  │
  ├─ 系统是否完全不可用？ ── → P0
  │
  ├─ 核心功能（上传/检索/RAG）是否完全失败？ ── → P1
  │
  ├─ 有无明确的 workaround？ ── → 优先 workaround，继续 P1/P2
  │
  └─ 仅视觉/文案/动画问题 ── → P3
```

### 1.3 Bug 逃逸率度量

```python
# metrics/bug_escape_rate.py

def bug_escape_rate():
    """
    Bug 逃逸率 = (生产环境发现的 Bug 数 / QA 阶段发现的 Bug 数) × 100%
    目标: < 5%
    """
    qa_found = count_bugs(status="resolved", source="qa")
    prod_found = count_bugs(status="resolved", source="production")

    rate = prod_found / (qa_found + prod_found)
    return rate

# 每周质量报告中:
# "本周: QA 发现 12 个 Bug, 生产逃逸 0 个, 逃逸率 0% (目标 <5%)"
```

---

## 2. PostgreSQL RLS（行级安全）测试（新增）

> API 层的隐私隔离测试通过不等于数据库层安全。如果攻击者绕过 API 直接连接数据库（凭证泄露、内部威胁），RLS 策略是最后防线。

### 2.1 RLS 隔离验证

```python
# tests/integration/test_postgres_rls.py

class TestPostgresRLS:
    """
    PostgreSQL 行级安全策略测试
    目标: 即使绕过 API，数据库层仍保证用户间数据隔离
    """

    def test_user_a_cannot_select_user_b_papers(self, db_connection_as_user_a):
        """
        直接 SQL: 用户 A 无法 SELECT 用户 B 的论文元数据
        """
        result = db_connection_as_user_a.execute("""
            SELECT id, title FROM papers WHERE user_id = 'user_b_id';
        """)
        assert result.rowcount == 0, "RLS 未生效: 用户 A 能查到用户 B 的论文"

    def test_user_a_cannot_select_user_b_vectors(self, db_connection_as_user_a):
        """
        直接 SQL: 用户 A 无法访问 Qdrant 中用户 B 的向量（通过元数据关联）
        """
        result = db_connection_as_user_a.execute("""
            SELECT paper_id, chunk_text
            FROM paper_chunks pc
            JOIN papers p ON pc.paper_id = p.id
            WHERE p.user_id = 'user_b_id'
            LIMIT 10;
        """)
        assert result.rowcount == 0, "RLS 未生效: 用户 A 能查到用户 B 的向量"

    def test_rls_applies_to_delete(self, db_connection_as_user_a):
        """
        直接 SQL: 用户 A 无法 DELETE 用户 B 的论文
        """
        with pytest.raises(permissions_error):
            db_connection_as_user_a.execute("""
                DELETE FROM papers WHERE user_id = 'user_b_id';
            """)

    def test_new_papers_auto_enforce_rls(self, db_connection_as_user_a):
        """
        新插入的论文自动受 RLS 保护，不需要手动 GRANT
        """
        # 用户 A 插入新论文
        new_paper_id = db_connection_as_user_a.execute("""
            INSERT INTO papers (title, user_id) VALUES ('New Paper', 'user_a_id')
            RETURNING id;
        """)[0]

        # 用户 A 能查到自己的新论文
        result = db_connection_as_user_a.execute("""
            SELECT id FROM papers WHERE id = %s;
        """, new_paper_id)
        assert result.rowcount == 1

        # 用户 B 查不到
        result_b = db_connection_as_user_b.execute("""
            SELECT id FROM papers WHERE id = %s;
        """, new_paper_id)
        assert result_b.rowcount == 0
```

---

## 3. 数据库迁移测试（新增）

### 3.1 迁移测试范围

| 迁移类型 | 测试策略 |
|---------|---------|
| **Schema 变更**（新增表/列/索引）| 升级 + 回滚 双向测试 |
| **数据迁移**（字段拆分/合并）| 迁移前后数据一致性验证 |
| **向量库 Schema 变更** | Qdrant collection 更新不影响已有数据 |
| **配置变更**（feature flag 新增枚举值）| 向后兼容验证 |

### 3.2 Alembic 迁移测试

```python
# tests/migrations/test_alembic_migrations.py

class TestDatabaseMigrations:
    """
    Alembic 双向迁移测试
    每次 schema 变更必须跑这套测试
    """

    def test_migration_up_and_down_idempotent(self, clean_db):
        """
        迁移 UP → DOWN → UP 后，数据库状态与单次 UP 完全等价
        """
        # 记录单次 UP 后的 schema fingerprint
        initial_fingerprint = get_schema_fingerprint(clean_db)

        # UP → DOWN → UP
        alembic_up()
        alembic_down()
        alembic_up()

        final_fingerprint = get_schema_fingerprint(clean_db)
        assert initial_fingerprint == final_fingerprint, \
            "双向迁移后 schema 不一致，可能是 down() 脚本不完整"

    def test_migration_preserves_user_data(self, db_with_test_user):
        """
        迁移过程中用户数据不丢失
        """
        # 记录迁移前用户数据
        user_papers_before = count_rows("papers", user_id=TEST_USER_ID)
        user_vectors_before = count_rows("paper_chunks", user_id=TEST_USER_ID)

        # 执行迁移
        alembic_upgrade("head")

        # 验证数据完整
        assert count_rows("papers", user_id=TEST_USER_ID) == user_papers_before
        assert count_rows("paper_chunks", user_id=TEST_USER_ID) == user_vectors_before

    @pytest.mark.parametrize("migration_id", get_pending_migrations())
    def test_each_pending_migration_is_reversible(self, clean_db, migration_id):
        """
        每一个 pending migration 都必须有对应的 down() 脚本，且可执行
        """
        alembic_upgrade(migration_id)
        # down() 不应抛出异常
        alembic_downgrade(migration_id, -1)
        assert migration_id in get_applied_migrations()  # 已回滚

    def test_downgrade_from_latest_returns_to_baseline(self, clean_db):
        """
        从最新版本完全回滚到基准版本（baseline）
        基线: alembic stamp head（假设的干净状态）
        """
        alembic_upgrade("head")
        alembic_downgrade("base")

        # 验证: 只有 base 版本标记的 migration
        applied = get_applied_migrations()
        assert len(applied) <= 1  # 只有一个 base migration
```

---

## 4. Feature Flag 测试策略（新增）

### 4.1 Feature Flag 架构

```python
# 使用 Feature Flag 服务（e.g., Unleash / LaunchDarkly）
# 标志定义示例:

FEATURE_FLAGS = {
    "new_rag_prompt_v2": {
        "description": "新 RAG prompt 模板（提升忠实度）",
        "default": False,
        "rollout_stages": {
            "internal": 100,       # 内部用户 100%
            "beta": 20,           # Beta 用户 20%
            "general": 0,          # 正式用户 0%（金丝雀）
        }
    },
    "bge_embedding_fallback": {
        "description": "OpenAI Embedding 失败时切换 BGE 本地模型",
        "default": True,
        "rollout_stages": {"internal": 100, "beta": 100, "general": 100}
    }
}
```

### 4.2 Feature Flag 测试矩阵

| 测试场景 | 覆盖标志 | 测试目标 |
|---------|---------|---------|
| Flag OFF → ON 平滑切换 | 全部 | 用户无感知，flag 切换不触发错误 |
| Flag ON → OFF 降级 | 全部 | 关闭后系统回到旧逻辑，无数据损坏 |
| 分阶段 rollout | `new_rag_prompt_v2` | 20% 用户跑新代码，80% 跑旧代码，互不影响 |
| Flag 与 A/B test 隔离 | 全部 | Flag 控制的逻辑与 analytics A/B 实验互不干扰 |
| Flag 依赖关系 | 假设 `feature_c` 依赖 `feature_b` | 父 flag OFF 时，子 flag 不生效 |

### 4.3 Feature Flag 集成测试

```python
# tests/feature_flags/test_flag_behavior.py

class TestFeatureFlags:
    """
    Feature Flag 行为测试
    """

    def test_new_rag_flag_toggles_correctly(self, client, db):
        """
        同一会话内，Flag 从 OFF → ON 切换后，用户应立刻走新 RAG 逻辑
        无需重新登录
        """
        # 初始: Flag OFF，使用旧 prompt
        set_feature_flag(user_id=USER, flag="new_rag_prompt_v2", value=False)
        response_old = chat(query="what is X?")
        old_answer = response_old["answer"]

        # Flag ON，切到新 prompt
        set_feature_flag(user_id=USER, flag="new_rag_prompt_v2", value=True)
        response_new = chat(query="what is X?")
        new_answer = response_new["answer"]

        # 答案可以不同，但不应报错（平滑切换）
        assert response_new.status_code == 200

    def test_flag_rollout_20percent_roughly_accurate(self):
        """
        20% rollout 时，大约 20% 的请求走新逻辑
        允许 ±5% 误差（统计显著性）
        """
        new_count = 0
        total = 1000

        for _ in range(total):
            user_id = str(uuid4())
            if is_flag_enabled(user_id, "new_rag_prompt_v2"):
                new_count += 1

        ratio = new_count / total
        assert 0.15 <= ratio <= 0.25, f"Rollout 比例 {ratio} 不在 15%-25% 范围"

    def test_flag_depends_on_parent(self):
        """
        子 Flag 依赖父 Flag: 父 OFF 时，子 Flag 不管定义如何都无效
        """
        # 父 flag OFF
        set_feature_flag(user_id=USER, flag="feature_b", value=False)

        # feature_c 定义为依赖 feature_b
        # 无论 feature_c 本身值是什么，应返回 False
        result = is_flag_enabled(user_id=USER, flag="feature_c")
        assert result == False, "子 Flag 应在父 Flag OFF 时自动失效"
```

---

## 5. API 版本兼容性测试（新增）

### 5.1 向后兼容性规则

```python
# API_COMPATIBILITY_RULES

"""
v1 API 向后兼容性要求:
─────────────────────────────────────────────────
1. 字段: 已有字段不能删除、不能改变类型
2. 枚举值: 已有枚举值不能删除，只能新增
3. 响应结构: 已有响应字段不能删除（可新增）
4. 行为: 已有端点语义不能改变
5. 错误码: 已有错误码不能改变含义

Breaking Changes（需要 API Version 升级）:
  - 删除字段
  - 改变字段类型
  - 删除或改变已有 API 端点
  - 改变认证方式
  - 删除或改变路径参数
"""

NON_BREAKING_CHANGES = [
    "新增可选字段",
    "新增 API 端点",
    "新增枚举值",
    "新增 query 参数",
    "放宽字段类型约束（如 string→any）",
]
```

### 5.2 API 兼容性测试

```python
# tests/api/test_backward_compatibility.py

class TestAPIBackwardCompatibility:
    """
    v1 API 向后兼容性测试
    每次 PR 必须通过此测试，确保不引入 Breaking Change
    """

    @pytest.mark.parametrize("endpoint", [
        "/api/v1/papers",
        "/api/v1/search",
        "/api/v1/chat",
        "/api/v1/collections",
    ])
    def test_known_fields_still_present(self, client, endpoint):
        """
        所有已知 v1 响应字段在当前代码中仍然存在
        """
        # 记录 OpenAPI spec 中定义的 v1 字段
        v1_schema = load_openapi_schema(version="v1")

        response = client.get(endpoint, headers=auth(USER))
        current_fields = set(response.json().keys())

        for field in v1_schema.required_fields:
            assert field in current_fields, \
                f"Breaking Change: 字段 {field} 在 {endpoint} 响应中消失"

    def test_new_enum_value_does_not_break_old_clients(self):
        """
        新增枚举值（如论文 status 新增 'processing'）时，
        旧客户端忽略未知值，不应崩溃
        """
        # 模拟旧客户端（只认已知的枚举值）
        response = client.get("/api/v1/papers/paper_id")

        # 旧客户端应忽略未知枚举值，不抛出异常
        assert response.status_code == 200

    def test_new_optional_field_does_not_break_parsing(self):
        """
        新增可选字段时，解析时不应因缺少该字段而报错
        """
        response = client.get("/api/v1/papers/paper_id")

        # 即使响应包含新字段，旧解析逻辑应忽略（不抛 KeyError）
        result = parse_paper_response(response.json())
        assert result is not None

    def test_api_version_header_present(self, client):
        """
        所有 v1 API 响应必须包含 X-API-Version 头
        """
        response = client.get("/api/v1/papers")
        assert "X-API-Version" in response.headers
        assert response.headers["X-API-Version"].startswith("v1")
```

---

## 6. i18n 测试（新增）

### 6.1 i18n 测试范围

| 场景 | 测试目标 |
|-----|---------|
| **语言切换** | en ↔ zh-CN 切换后，所有 UI 标签即时更新，不刷新页面 |
| **数字/日期格式** | 英文用 1,234.56 / 中文用 1,234.56；日期格式对应 |
| **长文本截断** | 中文标题过长时截断行为与英文一致（按字符，非按字节）|
| **搜索中英混合** | 搜索词含中文时，检索逻辑与纯英文一致 |
| **RAG 回答语言** | 用户用中文提问，RAG 回答用中文；英文提问用英文 |
| **邮件/通知模板** | 中英双语模板渲染正确 |

### 6.2 i18n 测试用例

```python
# tests/i18n/test_internationalization.py

class TestI18n:
    """
    国际化测试
    目标: 中英双语用户在各自语言环境下体验一致
    """

    def test_language_switch_updates_all_ui_labels(self, page):
        """
        语言切换: 所有静态标签即时更新，无需刷新
        """
        page.goto('/settings')
        page.select_option('[aria-label="语言"]', 'en')
        assert page.locator('[aria-label="Save"]').is_visible()

        page.select_option('[aria-label="语言"]', 'zh-CN')
        # 中文标签出现
        assert page.locator('[aria-label="保存"]').is_visible()
        # 英文标签消失
        assert not page.locator('[aria-label="Save"]').is_visible()

    def test_date_format_per_locale(self, page):
        """
        日期格式: en=Mar 30, 2026 / zh-CN=2026年3月30日
        """
        page.goto('/dashboard')

        page.evaluate("window.__locale='en'")
        page.reload()
        en_date = page.locator('.paper-date').first().text_content()
        assert "Mar" in en_date and "," in en_date  # Mar 30, 2026

        page.evaluate("window.__locale='zh-CN'")
        page.reload()
        zh_date = page.locator('.paper-date').first().text_content()
        assert "2026年" in zh_date  # 2026年3月30日

    def test_rag_answer_language_matches_query(self, page):
        """
        RAG 回答语言跟随用户提问语言
        """
        # 中文提问 → 中文回答
        page.fill('[aria-label="搜索论文或提问"]', '这篇论文的主要贡献是什么？')
        page.click('[aria-label="搜索"]')
        answer_cn = page.locator('.chat-bubble-ai').first().text_content()
        assert any('\u4e00' <= c <= '\u9fff' for c in answer_cn), \
            "中文提问后回答不含中文"

        # 英文提问 → 英文回答
        page.fill('[aria-label="搜索论文或提问"]', 'What is the main contribution?')
        page.click('[aria-label="搜索"]')
        answer_en = page.locator('.chat-bubble-ai').first().text_content()
        assert answer_en.isascii(), "英文提问后回答包含非ASCII字符"
```

---

## 7. Golden Dataset 管理规范（新增）

### 7.1 Golden Dataset 版本管理

```yaml
# tests/quality/golden_dataset/
# 结构:
# golden_rag/
#   ├── v1.0/
#   │   ├── queries.json      # 问答对
#   │   ├── papers/           # 论文 PDF（CC 协议）
#   │   └── expected.json     # 人工标注的期望答案/引用
#   ├── v1.1/
#   │   └── ... (增量更新)
#   └── README.md

# golden_dataset.yaml — 元数据管理
```

```python
# tests/quality/test_golden_dataset.py

class TestGoldenDataset:
    """
    Golden Dataset 质量保证测试
    Golden Dataset 是 RAG 质量评估的基准，必须保证其质量
    """

    def test_golden_queries_have_unique_intent(self):
        """
        每个 Golden Query 必须是独立意图，不重复
        防止 MRR 指标被人为刷高
        """
        queries = load_golden_queries()
        intents = [q["intent"] for q in queries]
        assert len(intents) == len(set(intents)), \
            "Golden Dataset 存在重复意图的查询对"

    def test_expected_answers_are_not_too_short(self):
        """
        期望答案长度必须 ≥ 20 字符
        防止"不知道"类的极短答案被误判为正确
        """
        for q in load_golden_queries():
            assert len(q["expected_answer"]) >= 20, \
                f"Query {q['id']} 期望答案过短: {q['expected_answer']}"

    def test_papers_in_golden_set_are_reachable(self):
        """
        Golden Dataset 中的论文必须可以通过 API 正常访问和索引
        防止索引 pipeline 损坏导致质量评估失败
        """
        for item in load_golden_queries():
            paper_id = item["paper_id"]
            response = client.get(f"/api/papers/{paper_id}")
            assert response.status_code == 200, \
                f"Golden Paper {paper_id} 无法访问，质量评估将失败"

    def test_golden_dataset_is_not_stale(self):
        """
        Golden Dataset 与当前 embedding 模型版本匹配
        当 embedding 模型更新时，golden dataset 需要重新标注
        """
        dataset_version = load_golden_metadata()["embedding_model_version"]
        current_version = get_current_embedding_version()

        assert dataset_version == current_version, \
            f"Golden Dataset 版本 {dataset_version} 与当前 embedding {current_version} 不匹配，" \
            f"需要重新生成 golden answers"
```

### 7.2 Golden Dataset 更新流程

```
发现 RAG 质量问题
    │
    ▼
QA 人工评估（是否 golden dataset 问题）
    │
    ├─ 是 → 收集新/修正的 query + expected_answer
    │        更新到 golden_rag/vX.X/
    │        记录 embedding_model_version
    │        PR 必须包含 golden dataset 变更
    │
    └─ 否 → 是 RAG pipeline 本身问题
             → 提 Bug (P1/P2) + 修复代码
```

---

## 8. 搜索排序回归测试（新增）

### 8.1 排序回归风险

> embedding 模型更新（v1 → v2）后，相同 query 的 top-10 结果可能发生顺序变化。
> 如果变差但没有检测机制，用户会感觉"搜索越来越不准"。

### 8.2 排序回归检测

```python
# tests/quality/test_search_ranking_regression.py

class TestSearchRankingRegression:
    """
    搜索排序回归测试
    embedding 模型更新后，必须跑此测试
    """

    @pytest.fixture
    def ranking_baseline(self):
        """加载上一次 embedding 模型的检索结果基线"""
        return load_json("tests/quality/baseline/ranking_v1.json")
        # 格式: { query: string, results: [paper_id, paper_id, ...] }

    def test_embedding_upgrade_does_not_degrade_mrr_significantly(self, ranking_baseline):
        """
        embedding 模型升级后，MRR 相对基线下降不超过 5%
        """
        baseline_mrr = ranking_baseline["mrr"]

        current_results = []
        for q in ranking_baseline["queries"]:
            results = await search(query=q["query"], user_id=TEST_USER, top_k=10)
            current_results.append(results)

        current_mrr = calculate_mrr(current_results, ranking_baseline["queries"])

        degradation = (baseline_mrr - current_mrr) / baseline_mrr
        assert degradation <= 0.05, \
            f"Embedding 升级导致 MRR 下降 {degradation:.1%}，超过 5% 上限，" \
            f"需要重新评估新 embedding 模型或回滚"

    def test_top3_stability(self, ranking_baseline):
        """
        top-3 结果的稳定性: 升级后 top-3 至少保留 2 个
        MRR 可能轻微下降，但 top 结果不应完全换血
        """
        for q in ranking_baseline["queries"]:
            baseline_top3 = set(q["results"][:3])
            current_results = await search(query=q["query"], user_id=TEST_USER, top_k=3)
            current_top3 = set(r.paper_id for r in current_results)

            overlap = len(baseline_top3 & current_top3)
            assert overlap >= 2, \
                f"Query '{q['query']}' top-3 变化过大: " \
                f"旧={baseline_top3}, 新={current_top3}, 重叠={overlap}"
```

---

## 9. 限流算法正确性测试（新增）

### 9.1 Token Bucket 算法验证

```python
# tests/integration/test_rate_limiting.py

class TestRateLimiting:
    """
    限流算法正确性测试
    不仅测"是否返回 429"，还测"限流算法本身是否正确实现"
    """

    def test_token_bucket_allows_burst(self):
        """
        Token Bucket 允许 burst: 初始以最大速率处理请求
        免费用户: 5 burst → 然后降速
        """
        responses = []
        start = time.time()

        # 在 bucket 刷新前连续发 5 个请求
        for _ in range(5):
            r = client.post("/api/search", json={"query": "test"})
            responses.append(r.status_code)
            sleep(0.05)  # 50ms 间隔

        elapsed = time.time() - start

        # 5 个请求全部成功（burst 允许）
        assert all(code == 200 for code in responses), \
            f"Token Bucket burst 被错误拒绝: {responses}"

        # 第 6 个请求应被限流（已超过 burst 上限）
        r6 = client.post("/api/search", json={"query": "test"})
        assert r6.status_code == 429

    def test_sliding_window_exactly_at_boundary(self):
        """
        滑动窗口在边界时刻的精确行为: 刚好 1 分钟前的那一分钟界线上
        """
        # 场景: 第 4 分钟 59 秒时发送请求
        # 1 分钟前 = 第 3 分钟，开始计数
        # 如果 3 分钟内发了 5 个请求，此时被限流

        # 制造 4:59 时刻的请求历史
        set_user_request_history(
            user_id=USER,
            timestamps=[
                datetime.now() - timedelta(minutes=3, seconds=30),
                datetime.now() - timedelta(minutes=3, seconds=10),
                datetime.now() - timedelta(minutes=2, seconds=50),
                datetime.now() - timedelta(minutes=1, seconds=40),
                datetime.now() - timedelta(minutes=0, seconds=30),
            ]
        )

        # 此时刻请求应被限流（5 个请求都在滑动窗口内）
        r = client.post("/api/search", json={"query": "test"})
        assert r.status_code == 429

        # 等到最老请求过期
        sleep(31)  # 30s 那个请求过期
        r2 = client.post("/api/search", json={"query": "test"})
        assert r2.status_code == 200, "最老请求过期后应允许新请求"

    def test_rate_limit_headers_return_correct_info(self):
        """
        429 响应头包含正确的限流信息（RFC 6585）
        """
        # 耗尽配额
        for _ in range(6):
            client.post("/api/search", json={"query": "test"})

        r = client.post("/api/search", json={"query": "test"})
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert "X-RateLimit-Limit" in r.headers
        assert "X-RateLimit-Remaining" in r.headers
```

---

## 10. Staging 环境数据策略（新增）

### 10.1 Staging 数据管理原则

```
Staging 环境 ≠ 生产数据的完全拷贝（合规风险）
Staging 环境 = 合成数据 + 脱敏生产采样数据的混合

目标: 测试人员在 Staging 上的体验与生产高度一致
```

### 10.2 Staging 数据配置

```python
# tests/conftest.py — Staging fixture

@pytest.fixture(scope="module")
def staging_env():
    """
    Staging 环境数据配置
    每 24h 自动刷新
    """
    return {
        # 用户数据: 合成 20 个用户，覆盖各种角色
        "users": generate_synthetic_users(count=20, roles=["free", "pro", "academic"]),

        # 论文数据: arXiv CC 协议论文 200 篇（真实数据，无合规风险）
        "papers": load_arxiv_cc_papers(count=200),

        # 向量数据: 基于上述 200 篇论文预生成向量
        "vectors": load_precomputed_vectors(count=200),

        # 聊天历史: 合成 50 轮对话（无真实用户内容）
        "chat_history": generate_synthetic_chat_sessions(count=50),

        # 配额数据: 每个用户配额状态真实模拟
        "quotas": {
            "free": {"papers": 20, "searches": 20},
            "pro": {"papers": 99999, "searches": 99999},
            "academic": {"papers": 99999, "searches": 99999, "members": 5},
        }
    }

@pytest.fixture(autouse=True)
def reset_staging_data(staging_env):
    """
    每个测试前重置 Staging 数据到干净状态
    防止测试间相互污染
    """
    reset_staging_database()
    seed_staging_data(staging_env)
    yield
    # 测试后不清理（保留现场供人工审查）
```

---

## 11. 快速冒烟测试集（新增）

> 完整 E2E 套件耗时 40min 过长。发布前需要一个 < 5min 的 P0 快速子集。

### 11.1 快速冒烟标准

| 标准 | 目标 |
|-----|------|
| **总耗时** | ≤ 5 分钟 |
| **场景数** | 8-12 个 |
| **覆盖** | P0 功能冒烟 + 隐私隔离 + 最高优安全 |
| **触发时机** | 每次 merge 到 main 前（Layer 1 的 P0 子集）|

### 11.2 快速冒烟场景矩阵

| # | 测试场景 | 时长估算 | 覆盖内容 |
|---|---------|---------|---------|
| 1 | 注册 → 上传 → 检索 | 90s | 核心路径 |
| 2 | RAG 问答（含引用） | 60s | RAG 核心功能 |
| 3 | 隐私隔离（用户A搜不到用户B论文） | 30s | 最高安全 |
| 4 | 论文删除后向量立即消失 | 30s | 数据清理完整性 |
| 5 | JWT 过期 → 自动刷新 → 继续操作 | 30s | 认证韧性 |
| 6 | PDF 上传失败 → 429 限流拦截 | 20s | 限流 |
| 7 | Dark Mode 切换 → 刷新后保持 | 15s | 主题持久化 |
| 8 | 批量删除 → 二次确认弹窗 | 20s | 危险操作安全 |

---

## 12. LangChain 组件测试策略（新增）

### 12.1 LangChain RAG Pipeline 测试

```python
# tests/unit/test_langchain_pipeline.py

class TestLangChainPipeline:
    """
    LangChain/LlamaIndex RAG pipeline 组件测试
    测试 LangChain Chain 本身的正确性，不只是 API 层
    """

    def test_retriever_returns_filtered_results(self, langchain_chain):
        """
        LangChain Retriever 正确应用 user_id filter
        不应返回其他用户的文档
        """
        retrieved = langchain_chain.retriever.get_relevant_documents(
            query="deep learning",
            user_id="user_a"
        )

        for doc in retrieved:
            assert doc.metadata["user_id"] == "user_a", \
                f"LangChain Retriever 返回了 user_id={doc.metadata['user_id']} 的文档"

    def test_chain_refuses_to_answer_without_context(self, langchain_chain):
        """
        LangChain Chain 在 context 为空时正确拒答，不幻觉
        """
        # monkey-patch retriever to return empty
        langchain_chain.retriever.get_relevant_documents = lambda *a, **kw: []

        response = langchain_chain.invoke({
            "question": "What is X?"
        })

        # 答案应表示"无法回答"或"上下文不足"
        refusal_phrases = ["无法", "没有提供", "上下文不足", "cannot answer"]
        assert any(p in response["answer"] for p in refusal_phrases), \
            "无上下文时 LangChain Chain 产生了幻觉答案"

    def test_citation_extractor_handles_malformed_citations(self):
        """
        引用抽取器对格式错误的引用（如空引用、无效页码）不崩溃
        """
        citations = extract_citations_from_response(
            "According to [,] and [P999] which doesn't exist."
        )
        # 应返回空列表或格式正确的引用，不抛出异常
        assert isinstance(citations, list)
```

---

## 13. 测试金字塔（v3.0 完整版）

```
                        ┌──────────────────────────────────┐
                        │   E2E (10%)                    │
                        │   Playwright (~20 个场景)      │
                        │   耗时: P0快速冒烟 ≤5min        │
                        │         完整套件 ≤40min        │
                       ─┴──────────────────────────────────┴──────────────────
                        │  集成测试 (20%)                          │
                        │  FastAPI TestClient + Testcontainers     │
                        │  ~80 个场景                              │
                        │  覆盖: API / DB RLS / 迁移 / i18n / 限流  │
                       ─┴──────────────────────────────────────────────┴──
                        │  单元测试 (70%)                          │
                        │  pytest + Jest                           │
                        │  ~400+ 个场景                            │
                        │  覆盖: 业务逻辑 / 向量指标 / JWT / PDF解析   │
                        │              / LangChain / Feature Flag   │
                       ─┴──────────────────────────────────────────────┴──
```

---

## 14. CI/CD 流水线（v3.0）

```yaml
# .github/workflows/ci.yml — v3.0 完整版

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  # ── Layer 0: pre-commit ────────────────────────────────
  lint-and-type:
    runs-on: ubuntu-latest
    steps: [ruff check, mypy --strict]

  unit-fast:
    needs: [lint-and-type]
    runs-on: ubuntu-latest
    steps:
      - docker compose up -d postgres redis qdrant
      - pytest tests/unit/ -m "not slow" --cov --cov-fail-under=80

  # ── Layer 1: PR ──────────────────────────────────────
  unit-all:
    needs: [unit-fast]
    runs-on: ubuntu-latest
    steps:
      - docker compose up -d
      - pytest tests/unit/ -v --cov --cov-fail-under=80

  integration-all:
    needs: [unit-all]
    runs-on: ubuntu-latest
    steps:
      - docker compose up -d
      - pytest tests/integration/ -v -x

      # 新增: RLS 隔离验证
      - pytest tests/integration/test_postgres_rls.py -v

      # 新增: 迁移测试
      - pytest tests/migrations/ -v

      # 新增: 限流算法测试
      - pytest tests/integration/test_rate_limiting.py -v

  e2e-smoke:
    needs: [integration-all]
    runs-on: ubuntu-latest
    steps:
      - docker compose up -d
      # 快速冒烟: ≤5min
      - npx playwright test tests/e2e/smoke.fast.spec.ts

  api-compatibility:
    needs: [unit-all]
    runs-on: ubuntu-latest
    steps:
      - pytest tests/api/test_backward_compatibility.py -v

  # ── Layer 2: Release ─────────────────────────────────
  e2e-full:
    needs: [e2e-smoke]
    runs-on: ubuntu-latest
    steps: [npx playwright test tests/e2e/ --project=chromium]

  rag-quality:
    needs: [e2e-full]
    steps:
      - pytest tests/quality/ -v
      - python scripts/check_quality_gate.py

  ranking-regression:
    needs: [e2e-full]
    steps:
      - pytest tests/quality/test_search_ranking_regression.py -v

  # ── Layer 3: Hotfix ─────────────────────────────────
  hotfix-checks:
    if: startsWith(github.ref, 'refs/tags/hotfix')
    runs-on: ubuntu-latest
    steps:
      - docker compose up -d
      - pytest tests/ -m "privacy or smoke" -v -x
      - pytest tests/integration/test_postgres_rls.py -v
```

---

## 15. 质量门槛（v3.0 完整版）

### 合并前（Layer 1）

| 指标 | 门槛 | 工具 |
|-----|------|------|
| 单元测试通过率 | 100% | pytest |
| 代码覆盖率 | ≥ 80% | Coverage.py |
| **PostgreSQL RLS 测试** | **100% 通过** | pytest |
| **数据库迁移双向测试** | **100% 通过** | pytest |
| 集成测试通过率 | 100% | pytest |
| **限流算法正确性** | **100% 通过** | pytest |
| **API 向后兼容性** | **Breaking Change = 0** | pytest |
| 隐私隔离测试 | 100% | pytest |
| E2E P0 快速冒烟 | 100% | Playwright |
| 安全注入测试 | 100% | pytest |
| Flaky 测试数 | 0 | 检测脚本 |

### 发布前（Layer 2）

| 指标 | 门槛 | 工具 |
|-----|------|------|
| RAG 引用召回率 | ≥ 85% | LLM-as-Judge |
| RAG 忠实度 | ≥ 0.8/1.0 | LLM-as-Judge |
| 向量检索 MRR | ≥ 基线 - 5% | 集成测试 |
| **搜索排序回归** | **top-3 稳定性 ≥ 66%** | 回归测试 |
| 性能基准测试 | 全部达标 | locust |
| 安全扫描 | 无高危漏洞 | Snyk + Safety |

---

## 16. Bug 分类 + 探索性测试策略

### 16.1 Bug 优先级与工程师职责

| Bug 级别 | 主要负责人 | 次要支持 |
|---------|---------|---------|
| **P0** | 全部工程师（on-call 轮值）| CTO + 全团队 |
| **P1** | 直接负责该模块的工程师 | QA + PM |
| **P2** | 模块负责人 | QA |
| **P3** | 任何有空的人 | — |

### 16.2 探索性测试会话（每 Sprint）

```python
# 每 Sprint 4 小时探索性测试，由 QA 执行
# Session 1 (1.5h): 论文上传 pipeline — 各种边缘 PDF
# Session 2 (1h):   RAG 问答 — 极端查询（无意义问题、超长查询）
# Session 3 (1h):   多用户并发 — 模拟 10 用户同时上传/检索
# Session 4 (0.5h): i18n — 中英混合场景

EXPLORATORY_CHARTER = """
焦点: 发现 RAG pipeline 在边界条件下的异常行为
准备: 20 篇不同格式的 PDF（含加密、损坏、超大、扫描件）
方法: 有重点的自由探索，每 15 分钟记录发现
出口标准: 发现 P0 → 立即停止 + 提Bug
         发现 P1/P2 → 记录但不中断
"""
```

---

## 17. 测试策略原则（v3.0）

> **"测试是收集信息的行为，不是验证软件符合规格。" — Michael Bolton**

| 原则 | 说明 |
|-----|------|
| **Bug 分类先于一切** | 没有共识的 Bug 级别 = 没有优先级的团队 |
| **数据库层是最后防线** | API 层隔离测试 ≠ 数据库层安全，PostgreSQL RLS 必须测试 |
| **迁移是公民义务** | 每次 schema 变更必须同时测试升级和回滚 |
| **Flag 是正式代码** | Feature Flag 逻辑和普通代码一样要求测试覆盖 |
| **排序是产品** | embedding 模型更新时，排序回归测试是必须的，不是可选的 |
| **Golden Dataset 是活的** | 需要版本管理，模型更新时必须同步更新 |
| **限流是安全边界** | Token Bucket 算法的正确性必须被测试，不能只测 429 返回码 |
| **快速冒烟是发布门槛** | < 5min P0 子集，完整套件不能成为发布的阻塞点 |
| **i18n 是功能** | 面向双语用户，切换语言是功能需求，不是"加分项" |

---

> 文件版本记录
> - v1.0 (17:58): 初始测试策略
> - v2.0 (18:02): 混沌/韧性、JWT安全、Flaky规范、金丝雀E2E、PDF质量量化、向量指标(Recall@K/MRR@K)、测试分层执行、安全测试、生产质量监控
> - **v3.0 (20:52): Bug分类体系(P0-P3)、PostgreSQL RLS测试、数据库迁移双向测试、Feature Flag测试(4场景)、API版本兼容性、i18n测试(6场景)、Golden Dataset版本管理规范、搜索排序回归、限流算法正确性(Token Bucket验证)、Staging数据真实性策略、快速冒烟子集(≤5min)、LangChain组件测试**
> - **v3.1 (21:28): 与 CEO v2.0 对齐 — Staging测试数据角色更新为 Free/Pro/Academic（非旧的 Team），团队协作相关测试不在 E2E 矩阵中（CEO v2.0 砍掉团队协作），批量操作测试标注为 Phase 2+（MVP 不含批量选择功能）**
