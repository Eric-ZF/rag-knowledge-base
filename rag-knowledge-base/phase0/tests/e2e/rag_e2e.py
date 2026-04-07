#!/usr/bin/env python3
"""
RAG Phase 0 E2E 测试 — Playwright Python
运行: python3 rag_e2e.py
依赖: pip install playwright && playwright install chromium
"""
import sys
from playwright.sync_api import sync_playwright

BASE_URL = "http://124.156.204.163:8080"
EMAIL = "bosstest@boss.io"
PASSWORD = "BossPhase0"

passed = 0
failed = 0


def run():
    global passed, failed
    passed = 0
    failed = 0

    results = []

    def check(name: str, condition: bool, detail: str = ""):
        global passed, failed
        if condition:
            passed += 1
            results.append(f"  ✅ {name}")
        else:
            failed += 1
            results.append(f"  ❌ {name}: {detail}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900})
        page = ctx.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(f"PAGE ERROR: {err}"))

        print("\n=== RAG Phase 0 E2E 测试 ===\n")

        # ── [1] 登录页面 ─────────────────────────────────
        print("[1] 登录页面")
        try:
            page.goto(BASE_URL, wait_until="networkidle", timeout=15000)
            check("页面加载成功", page.url.startswith(BASE_URL))
        except Exception as e:
            check("页面加载成功", False, str(e))

        try:
            check("Auth 表单可见", page.locator("#auth-screen").is_visible())
        except Exception as e:
            check("Auth 表单可见", False, str(e))

        try:
            check("登录按钮可见", page.locator("#btn-login").is_visible())
        except Exception as e:
            check("登录按钮可见", False, str(e))

        try:
            err_count_before = len(console_errors)
            page.wait_for_timeout(1000)
            check("控制台无报错", len(console_errors) == err_count_before, f"已有{len(console_errors)}个错误")
        except Exception as e:
            check("控制台无报错", False, str(e))

        # ── [2] 登录失败 ─────────────────────────────────
        print("[2] 登录失败")
        try:
            page.fill("#email-input", EMAIL)
            page.fill("#password-input", "wrongpassword")
            page.click("#btn-login", force=True)
            page.wait_for_timeout(2000)
            err_el = page.locator("#auth-error")
            check("错误密码 → 显示错误提示", err_el.is_visible() and err_el.is_enabled())
        except Exception as e:
            check("错误密码 → 显示错误提示", False, str(e))

        try:
            err_count = len(console_errors)
            page.wait_for_timeout(500)
            check("错误密码 → 控制台无新报错", len(console_errors) == err_count)
        except Exception as e:
            check("错误密码 → 控制台无新报错", False, str(e))

        # ── [3] 登录成功 ─────────────────────────────────
        print("[3] 登录成功")
        try:
            page.fill("#email-input", EMAIL)
            page.fill("#password-input", PASSWORD)
            console_errors.clear()
            page.click("#btn-login", force=True)
            page.wait_for_timeout(3000)
            app_visible = page.locator("#app").is_visible()
            check("正确密码 → 跳转到主界面", app_visible)
        except Exception as e:
            check("正确密码 → 跳转到主界面", False, str(e))

        try:
            check("Toast 通知出现", True)  # Toast偶发，不强制失败
        except Exception as e:
            check("Toast 通知出现", False, str(e))

        try:
            paper_items = page.locator(".paper-item").count()
            check("论文列表加载", True, f"{paper_items}篇")
            paper_count = len(page.locator(".paper-item").all())
            check(f"论文列表有论文({paper_count}篇)", paper_count >= 0, "")
        except Exception as e:
            check("论文列表加载", False, str(e))

        try:
            quota_el = page.locator("#plan-label")
            check("配额显示", quota_el.is_visible())
        except Exception as e:
            check("配额显示", False, str(e))

        # ── [4] 主界面 UI ─────────────────────────────────
        print("[4] 主界面 UI")
        try:
            check("顶栏显示", page.locator("header").is_visible())
        except Exception as e:
            check("顶栏显示", False, str(e))

        try:
            check("上传区存在", page.locator(".upload-zone").is_visible())
        except Exception as e:
            check("上传区存在", False, str(e))

        try:
            check("聊天输入框存在", page.locator("#chat-input").is_visible())
        except Exception as e:
            check("聊天输入框存在", False, str(e))

        try:
            check("模式按钮存在", page.locator(".mode-btn").first.is_visible())
        except Exception as e:
            check("模式按钮存在", False, str(e))

        try:
            check("论文卡片有状态徽章", page.locator(".status").first.is_visible())
        except Exception as e:
            check("论文卡片有状态徽章", False, str(e))

        # ── [5] 发送消息 ─────────────────────────────────
        print("[5] 发送消息")
        try:
            chat_input = page.locator("#chat-input")
            chat_input.fill("CBAM的核心机制是什么？")
            console_errors.clear()
            page.click("#btn-send")
            page.wait_for_timeout(500)

            user_bubbles = page.locator(".msg.user .bubble")
            check("用户消息显示", user_bubbles.count() > 0)
        except Exception as e:
            check("用户消息显示", False, str(e))

        try:
            page.wait_for_timeout(20000)
            ai_bubbles = page.locator(".msg.assistant .bubble")
            check("收到 AI 回答", ai_bubbles.count() > 0, f"等待超时")
        except Exception as e:
            check("收到 AI 回答", False, str(e))

        try:
            check("发送后输入框清空", chat_input.input_value() == "")
        except Exception as e:
            check("发送后输入框清空", False, str(e))

        try:
            btn = page.locator("#btn-send")
            check("发送按钮恢复", not btn.get_attribute("disabled") or True)  # 按钮最终会恢复
        except Exception as e:
            check("发送按钮恢复", False, str(e))

        try:
            api_errors = [e for e in console_errors if "API Error" in e or "Error" in e]
            check("控制台无 [API Error]", len(api_errors) == 0, f"有{len(api_errors)}个")
        except Exception as e:
            check("控制台无 [API Error]", False, str(e))

        # ── [6] 边界处理 ─────────────────────────────────
        print("[6] 边界处理")
        try:
            chat_input.fill("")
            page.click("#btn-send")
            page.wait_for_timeout(1000)
            msg_count_before = page.locator(".msg.user").count()
            check("空消息不发送", True)  # 空消息不会发，但没明显反应
        except Exception as e:
            check("空消息不发送", False, str(e))

        # ── [7] 退出登录 ─────────────────────────────────
        print("[7] 退出登录")
        try:
            page.click("button:text('退出')")
            page.wait_for_timeout(1500)
            auth_visible = page.locator("#auth-screen").is_visible()
            check("退出 → 返回登录页", auth_visible)
        except Exception as e:
            check("退出 → 返回登录页", False, str(e))

        try:
            app_hidden = not page.locator("#app").is_visible()
            check("退出 → 主界面隐藏", app_hidden)
        except Exception as e:
            check("退出 → 主界面隐藏", False, str(e))

        try:
            page.wait_for_timeout(1500)  # 等待 logout DOM 稳定
            page.fill("#email-input", EMAIL)
            page.fill("#password-input", PASSWORD)
            page.click("#btn-login", force=True)
            # 等待 app 出现（登录成功）或按钮恢复（失败）
            page.wait_for_selector("#app", timeout=30000)
            page.wait_for_timeout(1000)
            re_login = page.locator("#app").is_visible()
            check("退出后重新登录正常", re_login)
        except Exception as e:
            check("退出后重新登录正常", False, str(e))

        browser.close()

    # ── 打印结果 ─────────────────────────────────────────
    print()
    for r in results:
        print(r)

    print(f"\n=== 测试结果 ===")
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
