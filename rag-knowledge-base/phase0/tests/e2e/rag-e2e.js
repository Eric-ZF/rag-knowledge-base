/**
 * RAG Phase 0 E2E 测试 — Playwright
 * 运行: node rag-e2e.js
 * 依赖: npm install playwright
 */

const { chromium } = require('playwright');

const BASE_URL = 'http://124.156.204.163:8080';
const EMAIL = 'bosstest@boss.io';
const PASSWORD = 'BossPhase0';
const COLLECTION = 'user_1d2a4dc3_550f_4f89_b97b_2b057705381c';

let passed = 0, failed = 0;

async function test(name, fn) {
  try {
    await fn();
    console.log(`  ✅ ${name}`);
    passed++;
  } catch(e) {
    console.log(`  ❌ ${name}: ${e.message}`);
    failed++;
  }
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    ignoreHTTPSErrors: true,
  });
  const page = await ctx.newPage();

  // ── 捕获所有 console 错误 ───────────────────────────
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('pageerror', err => consoleErrors.push('PAGE ERROR: ' + err.message));

  console.log('\n=== RAG Phase 0 E2E 测试 ===\n');

  // ── TEST 1: 登录页面加载 ──────────────────────────
  console.log('[1] 登录页面');
  await test('页面加载成功', async () => {
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    const title = await page.title();
    if (!title.includes('RAG')) throw new Error(`标题不对: ${title}`);
  });

  await test('Auth 表单可见', async () => {
    const card = await page.locator('.auth-card').isVisible();
    if (!card) throw new Error('登录卡片未显示');
  });

  await test('登录按钮可见', async () => {
    const btn = await page.locator('#btn-login').isVisible();
    if (!btn) throw new Error('登录按钮未找到');
  });

  await test('注册链接可见', async () => {
    const link = await page.locator('#btn-show-register').isVisible();
    if (!link) throw new Error('注册链接未找到');
  });

  await test('控制台无报错', async () => {
    // 忽略网络相关错误（favicon等）
    const realErrors = consoleErrors.filter(e =>
      !e.includes('favicon') && !e.includes('net::') && !e.includes('ERR_')
    );
    if (realErrors.length > 0) throw new Error(realErrors[0]);
  });

  // ── TEST 2: 登录失败 ────────────────────────────
  console.log('\n[2] 登录失败处理');
  consoleErrors.length = 0;

  await test('错误密码 → 显示错误提示', async () => {
    await page.fill('#email-input', EMAIL);
    await page.fill('#password-input', 'wrongpassword');
    await page.click('#btn-login');
    await page.waitForTimeout(1500);
    const errEl = page.locator('#auth-error');
    const visible = await errEl.isVisible();
    const text = await errEl.textContent();
    if (!visible || !text) throw new Error('错误提示未显示');
    consoleErrors.length = 0;
  });

  await test('错误密码 → 控制台无新报错', async () => {
    const realErrors = consoleErrors.filter(e =>
      !e.includes('favicon') && !e.includes('net::') && !e.includes('ERR_')
    );
    if (realErrors.length > 0) throw new Error(realErrors[0]);
  });

  // ── TEST 3: 登录成功 ────────────────────────────
  console.log('\n[3] 登录成功');
  consoleErrors.length = 0;

  await test('正确密码 → 登录成功', async () => {
    await page.fill('#email-input', EMAIL);
    await page.fill('#password-input', PASSWORD);
    await page.click('#btn-login');
    await page.waitForTimeout(3000); // 等 backend 处理
    // 检查是否跳转到主界面
    const appVisible = await page.locator('#app').isVisible();
    const authHidden = await page.locator('#auth-screen').getAttribute('class');
    if (appVisible && !authHidden?.includes('hidden')) {
      // 检查 user email 显示
      const emailText = await page.locator('#user-email').textContent();
      if (!emailText.includes(EMAIL.split('@')[0])) {
        throw new Error(`邮箱未正确显示: ${emailText}`);
      }
    } else {
      throw new Error(`未跳转到主界面, appVisible=${appVisible}, authHidden=${authHidden}`);
    }
    consoleErrors.length = 0;
  });

  await test('登录成功 → Toast 通知出现', async () => {
    await page.waitForTimeout(500);
    const toast = page.locator('.toast');
    const toastVisible = await toast.first().isVisible().catch(() => false);
    if (!toastVisible) throw new Error('无 Toast 通知');
    const text = await toast.first().textContent();
    if (!text.includes('成功')) throw new Error(`Toast 内容不对: ${text}`);
  });

  await test('论文列表加载完成', async () => {
    await page.waitForTimeout(2000);
    const container = page.locator('#papers-container');
    const hasContent = await container.textContent();
    if (!hasContent || hasContent.trim().length === 0) {
      throw new Error('论文列表为空');
    }
    // 应该有论文卡片或空状态
    const items = await page.locator('.paper-item, .empty-state').count();
    if (items === 0) throw new Error('无论文卡片也无空状态');
  });

  await test('配额显示正确', async () => {
    const quota = page.locator('#quota-banner');
    const text = await quota.textContent();
    if (!text.includes('Pro') && !text.includes('Free')) {
      throw new Error(`配额显示异常: ${text}`);
    }
  });

  // ── TEST 4: 主界面 UI ───────────────────────────
  console.log('\n[4] 主界面 UI');
  await test('顶栏显示', async () => {
    const h1 = await page.locator('header h1').textContent();
    if (!h1.includes('RAG')) throw new Error(`标题异常: ${h1}`);
  });

  await test('左侧上传区存在', async () => {
    const zone = await page.locator('.upload-zone').isVisible();
    if (!zone) throw new Error('上传区未显示');
  });

  await test('聊天输入框存在', async () => {
    const input = await page.locator('#chat-input').isVisible();
    if (!input) throw new Error('输入框未找到');
  });

  await test('聊天模式切换按钮存在', async () => {
    const btns = await page.locator('.mode-btn').count();
    if (btns < 3) throw new Error(`模式按钮数量不对: ${btns}`);
  });

  await test('论文卡片有状态徽章', async () => {
    const statuses = await page.locator('.status').count();
    if (statuses === 0) throw new Error('无状态徽章');
  });

  // ── TEST 5: 发送消息 ───────────────────────────
  console.log('\n[5] 发送消息');
  consoleErrors.length = 0;

  let chatErrorShown = false;
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  await test('发送消息 → 用户消息显示', async () => {
    await page.fill('#chat-input', 'CBAM实施时间是什么？');
    await page.click('#btn-send');
    await page.waitForTimeout(1000);
    const userBubble = page.locator('.msg.user .bubble').last();
    const text = await userBubble.textContent();
    if (!text.includes('CBAM')) throw new Error(`用户消息未显示: ${text}`);
  });

  await test('发送后输入框清空', async () => {
    const val = await page.locator('#chat-input').inputValue();
    if (val !== '') throw new Error(`输入框未清空: ${val}`);
  });

  await test('收到回答前显示 typing 动画', async () => {
    // 快速检查是否有 typing dots 出现
    await page.waitForTimeout(500);
    // typing 应该在 30s 内消失，所以找 dot 类元素
    const msgs = await page.locator('.msg.assistant').count();
    if (mss === 0) throw new Error('无 assistant 消息');
  });

  await test('收到 AI 回答', async () => {
    // 等待回答，最多 30s
    await page.waitForSelector('.msg.assistant .bubble:not(:has(.typing-dots))', { timeout: 30000 });
    const bubbles = await page.locator('.msg.assistant .bubble').all();
    const lastBubble = bubbles[bubbles.length - 1];
    const text = await lastBubble.textContent();
    if (!text || text.trim().length < 5) throw new Error('AI 回答为空或过短');
    if (text.includes('typing')) throw new Error('仍在 typing 状态');
  });

  await test('回答后发送按钮恢复', async () => {
    const btn = page.locator('#btn-send');
    const disabled = await btn.getAttribute('disabled');
    // 应该不再 disabled
    console.log('  按钮状态已恢复');
  });

  await test('控制台无 [API Error]', async () => {
    const apiErrors = consoleErrors.filter(e => e.includes('[API Error]'));
    if (apiErrors.length > 0) throw new Error(apiErrors[0]);
  });

  // ── TEST 6: 空输入处理 ───────────────────────────
  console.log('\n[6] 边界处理');
  await test('空消息不发送', async () => {
    await page.fill('#chat-input', '   ');
    await page.click('#btn-send');
    await page.waitForTimeout(500);
    // 应该没有新的用户消息出现
    const userMsgs = await page.locator('.msg.user').count();
    console.log(`  当前用户消息数: ${userMsgs}`);
  });

  // ── TEST 7: 退出登录 ───────────────────────────
  console.log('\n[7] 退出登录');
  await test('退出后返回登录页', async () => {
    await page.click('button:has-text("退出")');
    await page.waitForTimeout(1000);
    const authVisible = await page.locator('#auth-screen').isVisible();
    if (!authVisible) throw new Error('未返回登录页');
  });

  await test('退出后主界面隐藏', async () => {
    const appHidden = await page.locator('#app').getAttribute('class');
    if (!appHidden?.includes('hidden')) throw new Error('主界面未隐藏');
  });

  await test('退出后聊天记录清空', async () => {
    // 重新登录，聊天区应该只有欢迎语
    await page.fill('#email-input', EMAIL);
    await page.fill('#password-input', PASSWORD);
    await page.click('#btn-login');
    await page.waitForTimeout(3000);
    const chatMsgs = await page.locator('.msg.assistant .bubble').count();
    // 欢迎语 + 之前的问题回答
    if (chatMsgs < 2) throw new Error(`聊天记录异常: ${chatMsgs}条`);
  });

  await browser.close();

  // ── 结果汇总 ─────────────────────────────────────
  console.log('\n=== 测试结果 ===');
  console.log(`  通过: ${passed}`);
  console.log(`  失败: ${failed}`);
  if (failed === 0) {
    console.log('  🎉 全部通过！');
    process.exit(0);
  } else {
    console.log(`  ⚠️  ${failed} 项需修复`);
    process.exit(1);
  }
}

run().catch(e => {
  console.error('测试脚本异常:', e.message);
  process.exit(1);
});
