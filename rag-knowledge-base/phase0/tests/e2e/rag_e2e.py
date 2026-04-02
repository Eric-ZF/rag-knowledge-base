#!/usr/bin/env python3
"""
RAG Phase 0 E2E 测试 — Playwright Python
运行: python3 rag_e2e.py
依赖: pip install playwright && playwright install chromium
"""

from playwright.sync_api import sync_playwright, Page, expect
import sys

BASE_URL = "http://124.156.204.163:8080"
EMAIL = "bosstest@boss.io"
PASSWORD = "BossPhase0"

passed = 0
failed = 0

def test(name: str):
    """装饰器：记录测试结果"""
    def decorator(fn):
        global passed, failed
        def wrapper(*args, **kwargs):
            global passed, failed
            try:
                fn(*args, **kwargs)
                print(f"  ✅ {name}")
                passed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1
        return wrapper
    return decorator

def run():
    global passed, failed

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(f"PAGE ERROR: {err}"))

        print("\n=== RAG Phase 0 E2E 测试 ===\n")

        # ── TEST 1: 登录页面 ─────────────────────────────────
        print("[1] 登录页面")

        @test("页面加载成功")
        def t1():
            page.goto(BASE_URL, wait_until="networkidle")
            assert "RAG" in page.title(), f"标题: {page.title()}"

        @test("Auth 表单可见")
        def t2():
            assert page.locator(".auth-card").is_visible()

        @test("登录按钮可见")
        def t3():
            assert page.locator("#btn-login").is_visible()

        @test("控制台无报错")
        def t4():
            real = [e for e in console_errors if not any(x in e for x in ["favicon", "net::"])]
            assert len(real) == 0, real[0] if real else ""

        # ── TEST 2: 登录失败 ─────────────────────────────────
        print("\n[2] 登录失败")

        @test("错误密码 → 显示错误提示")
        def t5():
            console_errors.clear()
            page.fill("#email-input", EMAIL)
            page.fill("#password-input", "wrongpassword")
            page.click("#btn-login")
            page.wait_for_timeout(2000)
            err = page.locator("#auth-error")
            assert err.is_visible(), "错误提示未显示"
            text = err.text_content()
            assert len(text) > 0, "错误文本为空"

        @test("错误密码 → 控制台无新报错")
        def t6():
            real = [e for e in console_errors if not any(x in e for x in ["favicon", "net::"])]
            assert len(real) == 0, real[0] if real else ""

        # ── TEST 3: 登录成功 ─────────────────────────────────
        print("\n[3] 登录成功")

        @test("正确密码 → 跳转到主界面")
        def t7():
            console_errors.clear()
            page.fill("#email-input", EMAIL)
            page.fill("#password-input", PASSWORD)
            page.click("#btn-login")
            page.wait_for_timeout(4000)
            app_class = page.locator("#app").get_attribute("class")
            assert app_class is None or "hidden" not in str(app_class), f"未跳转: {app_class}"
            assert page.locator("#app").is_visible(), "主界面未显示"

        @test("论文列表加载")
        def t8():
            page.wait_for_timeout(3000)
            container = page.locator("#papers-container")
            assert container.is_visible(), "论文容器未显示"
            # 应该有论文卡片或空状态
            items = page.locator(".paper-item, .empty-state").count()
            assert items > 0, f"无论文卡片也无空状态: count={items}"

        @test("配额显示")
        def t9():
            text = page.locator("#quota-banner").text_content()
            assert "Pro" in text or "Free" in text, f"配额异常: {text}"

        @test("Toast 通知出现")
        def t10():
            page.wait_for_timeout(800)
            toasts = page.locator(".toast")
            count = toasts.count()
            assert count > 0, "无 Toast 通知"
            text = toasts.first.text_content()
            assert "成功" in text or "login" in text.lower(), f"Toast 内容: {text}"

        # ── TEST 4: 主界面 UI ─────────────────────────────────
        print("\n[4] 主界面 UI")

        @test("顶栏显示")
        def t11():
            h1 = page.locator("header h1").text_content()
            assert "RAG" in h1, f"标题: {h1}"

        @test("上传区存在")
        def t12():
            assert page.locator(".upload-zone").is_visible()

        @test("聊天输入框存在")
        def t13():
            assert page.locator("#chat-input").is_visible()

        @test("模式按钮存在")
        def t14():
            count = page.locator(".mode-btn").count()
            assert count >= 3, f"模式按钮数量: {count}"

        @test("论文卡片有状态徽章")
        def t15():
            count = page.locator(".status").count()
            assert count > 0, "无状态徽章"

        # ── TEST 5: 发送消息 ─────────────────────────────────
        print("\n[5] 发送消息")

        @test("发送消息 → 用户消息显示")
        def t16():
            page.fill("#chat-input", "CBAM实施时间是？")
            page.click("#btn-send")
            page.wait_for_timeout(1000)
            bubbles = page.locator(".msg.user .bubble").all()
            last = bubbles[-1].text_content()
            assert "CBAM" in last, f"用户消息: {last}"

        @test("发送后输入框清空")
        def t17():
            val = page.locator("#chat-input").input_value()
            assert val == "", f"输入框未清空: {val}"

        @test("收到 AI 回答（30s 内）")
        def t18():
            # 等待至少2条 assistant 消息（欢迎语 + 回答）
            def check_answer():
                msgs = page.locator(".msg.assistant .bubble:not(:has(.typing-dots))").all()
                if len(msgs) >= 2:
                    last = msgs[-1].text_content()
                    if last and len(last) > 5 and "typing" not in last.lower():
                        return True
                return False
            
            import time
            start = time.time()
            while time.time() - start < 30:
                if check_answer():
                    return
                page.wait_for_timeout(1000)
            raise AssertionError("30s 内未收到有效回答")

        @test("回答后发送按钮恢复")
        def t19():
            disabled = page.locator("#btn-send").get_attribute("disabled")
            assert disabled is None, "按钮仍为 disabled"

        @test("控制台无 [API Error]")
        def t20():
            real = [e for e in console_errors if "[API Error]" in e]
            assert len(real) == 0, real[0] if real else ""

        # ── TEST 6: 边界处理 ─────────────────────────────────
        print("\n[6] 边界处理")

        @test("空消息不发送")
        def t21():
            page.fill("#chat-input", "   ")
            page.click("#btn-send")
            page.wait_for_timeout(500)
            # 应该没有新的用户消息
            user_msgs = page.locator(".msg.user").count()
            assert user_msgs == 1, f"空消息被发送了: {user_msgs}条"

        # ── TEST 7: 退出登录 ─────────────────────────────────
        print("\n[7] 退出登录")

        @test("退出 → 返回登录页")
        def t22():
            page.click("button:has-text('退出')")
            page.wait_for_timeout(1000)
            assert page.locator("#auth-screen").is_visible(), "未返回登录页"

        @test("退出 → 主界面隐藏")
        def t23():
            cls = page.locator("#app").get_attribute("class")
            assert cls and "hidden" in str(cls), f"主界面未隐藏: {cls}"

        @test("退出后重新登录正常")
        def t24():
            page.fill("#email-input", EMAIL)
            page.fill("#password-input", PASSWORD)
            page.click("#btn-login")
            page.wait_for_timeout(4000)
            assert page.locator("#app").is_visible(), "重新登录后主界面未显示"

        browser.close()

    # ── 结果汇总 ──────────────────────────────────────────────
    print("\n=== 测试结果 ===")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    if failed == 0:
        print("  🎉 全部通过！")
        return 0
    else:
        print(f"  ⚠️  {failed} 项需修复")
        return 1

if __name__ == "__main__":
    sys.exit(run())
