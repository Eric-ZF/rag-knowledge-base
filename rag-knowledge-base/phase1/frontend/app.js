/**
 * Phase 1 — 前端 SPA 核心逻辑
 * 四页面：文献检索 / 智能问答 / 文献比较
 */

// ─── 配置 ────────────────────────────────────────
const API_BASE = "/api/v1";

// ─── 状态 ────────────────────────────────────────
const state = {
  page: "search",
  token: localStorage.getItem("token") || "",
  userEmail: localStorage.getItem("user_email") || "",
  papers: [],
  selectedPaperId: null,
  chatMode: "default",
  chatHistory: [],
  comparePapers: [],
  evidenceChunks: [],
};

// ─── 工具 ────────────────────────────────────────
function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function toast(msg, type = "info") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${type}`;
  setTimeout(() => el.classList.add("hidden"), 3500);
}

async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  const r = await fetch(API_BASE + path, { ...opts, headers: { ...headers, ...opts.headers } });
  if (r.status === 401) { localStorage.clear(); location.reload(); return; }
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

// ─── 页面路由 ────────────────────────────────────
function navigate(page) {
  state.page = page;
  $$(".page").forEach(p => p.classList.remove("active"));
  $$(".nav-btn").forEach(b => b.classList.remove("active"));
  $(`#page-${page}`)?.classList.add("active");
  $(`.nav-btn[data-page="${page}"]`)?.classList.add("active");
  history.replaceState(null, "", `#${page}`);
  onPageChange(page);
}

function onPageChange(page) {
  if (page === "search") loadPapers();
  if (page === "chat") updatePapersBadge();
  if (page === "compare") renderCompareTable();
}

// ─── 论文检索页 ──────────────────────────────────
async function loadPapers(filters = {}) {
  try {
    const data = await api("/papers");
    state.papers = data;
    renderPaperList(data);
  } catch (e) {
    toast("加载论文失败: " + e.message, "error");
  }
}

function renderPaperList(papers) {
  const list = $("#paper-list");
  $("#paper-count").textContent = `${papers.length} 篇`;
  if (!papers.length) {
    list.innerHTML = '<div class="empty-state"><div class="empty-icon">📄</div><div class="empty-title">暂无文献</div></div>';
    return;
  }
  list.innerHTML = papers.map(p => `
    <div class="paper-card${p.paper_id === state.selectedPaperId ? ' selected' : ''}" data-id="${p.paper_id}">
      <div class="paper-card-title">${escHtml(p.title)}</div>
      <div class="paper-card-meta">
        ${p.year ? `<span>${p.year}</span>` : ""}
        ${p.language ? `<span>${p.language === "zh" ? "中文" : "英文"}</span>` : ""}
        ${p.source ? `<span>${escHtml(p.source)}</span>` : ""}
      </div>
    </div>
  `).join("");

  list.querySelectorAll(".paper-card").forEach(card => {
    card.addEventListener("click", () => {
      state.selectedPaperId = card.dataset.id;
      list.querySelectorAll(".paper-card").forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      showPaperDrawer(card.dataset.id);
    });
  });
}

async function showPaperDrawer(paperId) {
  const drawer = $("#paper-drawer");
  drawer.classList.remove("hidden");
  const [paper, sections, profile] = await Promise.all([
    api(`/papers/${paperId}`),
    api(`/papers/${paperId}/sections`),
    api(`/papers/${paperId}/profile`).catch(() => null),
  ]);
  const authors = JSON.parse(paper.authors || "[]");
  const keywords = JSON.parse(paper.keywords || "[]");
  $("#drawer-content").innerHTML = `
    <div class="drawer-section">
      <h4>基本信息</h4>
      <div class="drawer-title">${escHtml(paper.title)}</div>
      ${authors.length ? `<div class="drawer-authors">${authors.join("；")}</div>` : ""}
    </div>
    ${paper.abstract ? `<div class="drawer-section"><h4>摘要</h4><div class="drawer-abstract">${escHtml(paper.abstract)}</div></div>` : ""}
    ${keywords.length ? `<div class="drawer-section"><h4>关键词</h4><div style="display:flex;gap:4px;flex-wrap:wrap">${keywords.map(k=>`<span class="method-tag">${escHtml(k)}</span>`).join("")}</div></div>` : ""}
    ${profile ? `
    <div class="drawer-section">
      <h4>文献画像</h4>
      <div class="profile-grid">
        <div class="profile-item"><div class="label">研究问题</div><div class="value">${profile.research_question || "—"}</div></div>
        <div class="profile-item"><div class="label">数据来源</div><div class="value">${profile.data_source || "—"}</div></div>
        <div class="profile-item"><div class="label">研究方法</div><div class="value">${JSON.parse(profile.methods || "[]").join(", ") || "—"}</div></div>
        <div class="profile-item"><div class="label">时间范围</div><div class="value">${profile.time_span || "—"}</div></div>
        <div class="profile-item"><div class="label">异质性</div><div class="value">${profile.heterogeneity || "—"}</div></div>
        <div class="profile-item"><div class="label">政策启示</div><div class="value">${profile.policy_implication || "—"}</div></div>
      </div>
    </div>
    ` : ""}
    <div class="drawer-section">
      <h4>章节结构（${sections.length} 节）</h4>
      ${sections.slice(0, 10).map(s => `<div style="font-size:12px;padding:4px 0;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between"><span>${escHtml(s.title || s.path)}</span><span style="color:#94a3b8">${s.page_start || ""}${s.page_end ? `-${s.page_end}` : ""}</span></div>`).join("")}
    </div>
  `;
}

function escHtml(s) {
  if (!s) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// ─── 智能问答页 ──────────────────────────────────
function updatePapersBadge() {
  const count = state.papers.length || 0;
  $("#papers-badge").textContent = `基于 ${count} 篇论文`;
}

let chatController = null;

async function sendChat() {
  const input = $("#chat-input");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  $("#char-count-num").textContent = "0";

  const messages = $("#chat-messages");
  // 移除空状态
  const empty = messages.querySelector(".empty-state");
  if (empty) empty.remove();

  // 用户消息
  messages.innerHTML += `<div class="msg-user">${escHtml(question)}</div>`;

  // 助手消息（typing 动画）
  const assistantDiv = document.createElement("div");
  assistantDiv.className = "msg-assistant";
  assistantDiv.innerHTML = `<div class="msg-typing"><span></span><span></span><span></span></div>`;
  messages.appendChild(assistantDiv);
  messages.scrollTop = messages.scrollHeight;

  try {
    chatController = new AbortController();
    const data = await api("/chat", {
      method: "POST",
      body: JSON.stringify({
        question,
        mode: state.chatMode,
        top_k: 8,
      }),
      signal: chatController.signal,
    });

    // 替换 typing 动画为真实答案
    assistantDiv.innerHTML = formatAnswer(data.answer, data.citations);
    state.evidenceChunks = data.citations || [];
    renderEvidencePanel(state.evidenceChunks);

    // 记录到历史
    state.chatHistory.unshift({ question, answer: data.answer, citations: data.citations, mode: state.chatMode });
    renderChatHistory();

  } catch (e) {
    if (e.name === "AbortError") {
      assistantDiv.innerHTML = "<em>已取消</em>";
    } else {
      assistantDiv.innerHTML = `<span style="color:var(--error)">❌ 错误: ${escHtml(e.message)}</span>`;
    }
  }
  messages.scrollTop = messages.scrollHeight;
}

function formatAnswer(answer, citations = []) {
  // 简单处理：检测 [n] 引用格式
  const citationMap = {};
  citations.forEach(c => { citationMap[c.index] = c; });

  let html = answer
    .replace(/\n/g, "<br/>")
    .replace(/\[(\d+)\]/g, (_, n) => {
      const c = citationMap[parseInt(n)];
      if (!c) return _;
      return `<span class="citation" data-chunk-id="${c.chunk_id}" title="${escHtml(c.paper_title)}">[${n}]</span>`;
    });

  // 绑定引用点击
  setTimeout(() => {
    assistantDiv.querySelectorAll(".citation").forEach(el => {
      el.addEventListener("click", () => showEvidenceDetail(el.dataset.chunkId));
    });
  }, 0);
  return html;
}

function renderChatHistory() {
  const list = $("#chat-history-list");
  list.innerHTML = state.chatHistory.slice(0, 10).map((h, i) => `
    <div class="chat-history-item" data-i="${i}">${escHtml(h.question.slice(0, 30))}${h.question.length > 30 ? "…" : ""}</div>
  `).join("");
}

function renderEvidencePanel(citations) {
  const panel = $("#evidence-panel");
  const list = $("#evidence-list");
  if (!citations || !citations.length) { panel.classList.add("hidden"); return; }
  panel.classList.remove("hidden");
  list.innerHTML = citations.map(c => `
    <div class="evidence-card" data-id="${c.chunk_id}">
      <div class="evidence-card-title">${escHtml(c.paper_title)}</div>
      <div class="evidence-card-meta">${c.chunk_type === "body" ? "" : `[${c.chunk_type}]`} ${c.page_range || ""}</div>
      <div class="evidence-card-preview">${escHtml(c.preview)}</div>
    </div>
  `).join("");

  list.querySelectorAll(".evidence-card").forEach(el => {
    el.addEventListener("click", () => showEvidenceDetail(el.dataset.id));
  });
}

async function showEvidenceDetail(chunkId) {
  const data = await api(`/chunks/${chunkId}`).catch(() => null);
  if (!data) return;
  // 简单弹出 alert，后续可扩展为 modal
  const preview = data.chunk_text?.slice(0, 300) || "";
  toast(`${data.paper_id}\n${preview}…`, "info");
}

// ─── 文献比较页 ──────────────────────────────────
function renderCompareTable() {
  const table = $("#compare-table");
  const body = $("#compare-body");
  const selected = state.comparePapers;

  if (selected.length < 2) {
    body.innerHTML = `<tr><td colspan="10" style="text-align:center;padding:40px;color:var(--text-secondary)">请从文献检索页选择至少 2 篇论文进行比较</td></tr>`;
    return;
  }

  const dims = [
    ["研究问题", "research_question"],
    ["研究对象", "research_object"],
    ["数据来源", "data_source"],
    ["时间范围", "time_span"],
    ["研究方法", "methods"],
    ["核心结论", "main_findings"],
    ["异质性发现", "heterogeneity"],
    ["政策启示", "policy_implication"],
    ["局限性", "limitations"],
  ];

  // 表头
  table.querySelector("thead tr").innerHTML =
    `<th class="sticky-col">维度</th>` +
    selected.map(p => `<th style="min-width:200px">${escHtml(p.title)}</th>`).join("");

  body.innerHTML = dims.map(([label, key]) => `
    <tr class="compare-dim-row">
      <td class="sticky-col">${label}</td>
      ${selected.map(p => `<td>${escHtml((p[key] || p[key.replace("_","")] || "—"))}</td>`).join("")}
    </tr>
  `).join("");
}

// ─── 事件绑定 ────────────────────────────────────
function bindEvents() {
  // 导航
  $$(".nav-btn").forEach(btn => {
    btn.addEventListener("click", e => { e.preventDefault(); navigate(btn.dataset.page); });
  });

  // 哈希路由
  window.addEventListener("hashchange", () => {
    const page = location.hash.slice(1) || "search";
    if (["search", "chat", "compare"].includes(page)) navigate(page);
  });

  // 论文抽屉关闭
  $("#drawer-close")?.addEventListener("click", () => $("#paper-drawer")?.classList.add("hidden"));

  // 筛选
  $("#filter-apply")?.addEventListener("click", () => {
    const kw = $("#filter-keyword")?.value.trim();
    const from = parseInt($("#filter-year-from")?.value) || null;
    const to = parseInt($("#filter-year-to")?.value) || null;
    const lang = $("#filter-language")?.value || null;
    let filtered = state.papers;
    if (kw) filtered = filtered.filter(p => p.title?.toLowerCase().includes(kw.toLowerCase()));
    if (from) filtered = filtered.filter(p => p.year >= from);
    if (to) filtered = filtered.filter(p => p.year <= to);
    if (lang) filtered = filtered.filter(p => p.language === lang);
    renderPaperList(filtered);
  });

  $("#filter-reset")?.addEventListener("click", () => {
    ["filter-keyword","filter-year-from","filter-year-to"].forEach(id => $(`#${id}`).value = "");
    $("#filter-language").value = "";
    renderPaperList(state.papers);
  });

  // 问答模式
  $$('input[name="chat-mode"]').forEach(radio => {
    radio.addEventListener("change", () => {
      state.chatMode = radio.value;
      $$(".radio-card").forEach(card => card.classList.remove("selected"));
      radio.closest(".radio-card").classList.add("selected");
    });
  });

  // 发送消息
  $("#chat-submit")?.addEventListener("click", sendChat);
  $("#chat-input")?.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  $("#chat-input")?.addEventListener("input", () => {
    $("#char-count-num").textContent = $("#chat-input").value.length;
  });

  // 退出
  $("#logout-btn")?.addEventListener("click", () => {
    localStorage.clear();
    location.reload();
  });

  // 比较页
  $("#compare-add")?.addEventListener("click", () => {
    if (state.selectedPaperId) {
      const paper = state.papers.find(p => p.paper_id === state.selectedPaperId);
      if (paper && !state.comparePapers.find(p => p.paper_id === paper.paper_id)) {
        state.comparePapers.push(paper);
        renderCompareTable();
        toast(`已添加: ${paper.title}`, "success");
      }
    } else {
      toast("请先从文献检索页选择一篇论文", "info");
    }
  });

  $("#compare-export-csv")?.addEventListener("click", exportCSV);
  $("#compare-export-md")?.addEventListener("click", exportMD);
}

function exportCSV() {
  const table = $("#compare-table");
  const rows = table.querySelectorAll("tr");
  let csv = "";
  rows.forEach(row => {
    const cells = row.querySelectorAll("th, td");
    csv += [...cells].map(c => `"${c.textContent.replace(/"/g,'""')}"`).join(",") + "\n";
  });
  download(`${document.title}_比较.csv`, csv, "text/csv");
}

function exportMD() {
  const table = $("#compare-table");
  const rows = table.querySelectorAll("tr");
  let md = "";
  rows.forEach(row => {
    const cells = row.querySelectorAll("th, td");
    md += [...cells].map((c, i) => i === 0 ? `**${c.textContent}**` : c.textContent).join(" | ") + "\n";
  });
  download(`${document.title}_比较.md`, md, "text/markdown");
}

function download(filename, content, type) {
  const blob = new Blob([content], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
}

// ─── 初始化 ──────────────────────────────────────
async function init() {
  // 恢复登录状态
  if (state.token) {
    try {
      const me = await api("/me").catch(() => null);
      if (me?.email) {
        state.userEmail = me.email;
        $("#user-email").textContent = me.email;
      }
    } catch {}
  }

  bindEvents();

  // 恢复路由
  const initialPage = location.hash.slice(1) || "search";
  navigate(["search","chat","compare"].includes(initialPage) ? initialPage : "search");
}

init();
