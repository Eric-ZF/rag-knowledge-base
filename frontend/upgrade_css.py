#!/usr/bin/env python3
"""Elicit-style CSS upgrade for index.html"""
import re

with open('/root/.openclaw/workspace/rag-knowledge-base/phase0/frontend/index.html') as f:
    html = f.read()

# ── 1. 升级 Google Fonts（添加 Inter）──────────────────────────────
old_fonts = '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">'
new_fonts = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600&display=swap" rel="stylesheet">'
html = html.replace(old_fonts, new_fonts)

# ── 2. 添加 Lucide Icons CDN（在 marked.js 之后）────────────────
lucide = '<script src="https://cdn.jsdelivr.net/npm/lucide@latest/dist/umd/lucide.min.js"></script>\n'
html = html.replace('</head>', lucide + '</head>')

# ── 3. 替换 CSS Variables + 全局样式 ───────────────────────────
old_css_vars = """      --ink-900: #1a1a2e;
      --ink-700: #2d2d44;
      --ink-500: #5c5c7a;
      --ink-400: #9b97a8;
      --paper:   #faf9f7;
      --accent:  #2563EB;          /* 专业学术蓝 */
      --accent-hover: #1D4ED8;
      --border:  #e8e6e3;
      --success: #059669;          /* 绿色：成功/已索引 */
      --danger:  #DC2626;          /* 红色：错误/删除 */
      --warning: #D97706;           /* 橙色：警告/处理中 */
      --shadow:  0 2px 8px rgba(0,0,0,0.08);
      --shadow-hover: 0 4px 16px rgba(0,0,0,0.12);
      --shadow-lg: 0 4px 24px rgba(0,0,0,0.1);
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
    }

    /* ── Dark mode ─────────────────────────────────────────── */
    @media (prefers-color-scheme: dark) {
      :root {
        --ink-900: #f0eeeb;
        --ink-700: #e0dee9;
        --ink-500: #a8a5b8;
        --ink-400: #7c7a8c;
        --paper:   #1a1a2e;
        --accent:  #60a5fa;
        --accent-hover: #3B82F6;
        --border:  #2d2d44;
        --shadow:  0 2px 8px rgba(0,0,0,0.3);
        --shadow-hover: 0 4px 16px rgba(0,0,0,0.4);
        --shadow-lg: 0 4px 24px rgba(0,0,0,0.3);
      }
    }

    body {
      font-family: 'IBM Plex Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
      background: var(--paper);
      color: var(--ink-700);
      min-height: 100vh;
    }"""

new_css_vars = """      /* ─── Elicit 学术风格色板 ─────────────────────────── */
      --ink-900: #0f172a;
      --ink-800: #1e293b;
      --ink-700: #334155;
      --ink-600: #475569;
      --ink-500: #64748b;
      --ink-400: #94a3b8;
      --ink-300: #cbd5e1;
      --paper:   #ffffff;
      --paper-2: #f8fafc;
      --paper-3: #f1f5f9;
      --accent:  #4f46e5;          /* Indigo — 专业学术紫 */
      --accent-hover: #4338ca;
      --accent-light: rgba(79,70,229,0.08);
      --accent-border: rgba(79,70,229,0.18);
      --success: #059669;          /* Emerald */
      --success-bg: rgba(5,150,105,0.08);
      --danger:  #dc2626;
      --danger-bg: rgba(220,38,38,0.08);
      --warning: #d97706;
      --warning-bg: rgba(217,119,6,0.08);
      --info:    #0284c7;
      --info-bg: rgba(2,132,199,0.08);
      --gradient-primary: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
      --gradient-hero: linear-gradient(160deg, #f8fafc 0%, #eef2ff 100%);
      --gradient-card-hover: linear-gradient(135deg, rgba(79,70,229,0.04) 0%, rgba(124,58,237,0.08) 100%);
      --border:  #e2e8f0;
      --border-2: #cbd5e1;
      --shadow:  0 1px 3px rgba(0,0,0,0.06), 0 4px 12px rgba(0,0,0,0.04);
      --shadow-hover: 0 4px 20px rgba(79,70,229,0.13), 0 1px 4px rgba(0,0,0,0.06);
      --shadow-lg: 0 8px 32px rgba(0,0,0,0.1);
      --shadow-xl: 0 20px 60px rgba(0,0,0,0.14);
      --radius-xs: 4px;
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 16px;
      --radius-xl: 24px;
    }

    /* ── Dark mode ─────────────────────────────────────────── */
    @media (prefers-color-scheme: dark) {
      :root {
        --ink-900: #f1f5f9;
        --ink-800: #e2e8f0;
        --ink-700: #cbd5e1;
        --ink-600: #94a3b8;
        --ink-500: #64748b;
        --ink-400: #475569;
        --ink-300: #334155;
        --paper:   #0f172a;
        --paper-2: #1e293b;
        --paper-3: #1e293b;
        --accent:  #818cf8;
        --accent-hover: #a5b4fc;
        --accent-light: rgba(129,140,248,0.1);
        --accent-border: rgba(129,140,248,0.25);
        --success-bg: rgba(5,150,105,0.12);
        --danger-bg: rgba(220,38,38,0.12);
        --warning-bg: rgba(217,119,6,0.12);
        --info-bg: rgba(56,189,248,0.12);
        --gradient-primary: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        --gradient-hero: linear-gradient(160deg, #0f172a 0%, #1e1b4b 100%);
        --border:  #1e293b;
        --border-2: #334155;
        --shadow:  0 1px 3px rgba(0,0,0,0.3), 0 4px 12px rgba(0,0,0,0.2);
        --shadow-hover: 0 4px 20px rgba(129,140,248,0.15), 0 1px 4px rgba(0,0,0,0.3);
        --shadow-lg: 0 8px 32px rgba(0,0,0,0.4);
        --shadow-xl: 0 20px 60px rgba(0,0,0,0.5);
      }
    }

    body {
      font-family: 'Inter', 'Noto Sans SC', 'PingFang SC', system-ui, sans-serif;
      font-feature-settings: 'cv02', 'cv03', 'cv04', 'cv11', 'ss01';
      background: var(--paper-2);
      color: var(--ink-700);
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }"""

html = html.replace(old_css_vars, new_css_vars)

# ── 4. 替换 Toast 样式（保留动画，升级配色）─────────────────────
old_toast = """.toast { padding: 10px 16px; border-radius: var(--radius-md); font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 8px; max-width: 320px; box-shadow: 0 4px 16px rgba(0,0,0,0.15); animation: toastIn 0.25s cubic-bezier(0.34, 1.56, 0.64, 1) both; pointer-events: auto; }
    .toast.success { background: #1a5c3a; color: #fff; }
    .toast.error   { background: var(--danger); color: #fff; }
    .toast.info    { background: var(--ink-700); color: #fff; }
    .toast.warning  { background: var(--warning); color: #fff; }"""

new_toast = """.toast { padding: 11px 16px; border-radius: var(--radius-md); font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 10px; max-width: 360px; box-shadow: var(--shadow-lg); animation: toastIn 0.3s cubic-bezier(0.34,1.56,0.64,1) both; pointer-events: auto; border: 1px solid transparent; }
    .toast.success { background: #064e3b; color: #6ee7b7; border-color: rgba(110,231,183,0.2); }
    .toast.error   { background: #7f1d1d; color: #fca5a5; border-color: rgba(252,165,165,0.2); }
    .toast.info    { background: #1e3a5f; color: #93c5fd; border-color: rgba(147,197,253,0.2); }
    .toast.warning  { background: #78350f; color: #fcd34d; border-color: rgba(252,211,77,0.2); }"""

html = html.replace(old_toast, new_toast)

# ── 5. 升级 Header ──────────────────────────────────────────────
old_header = """    header { height: 56px; border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 24px; gap: 16px; position: sticky; top: 0; background: var(--paper); z-index: 10; }
    header h1 { font-size: 16px; font-weight: 600; color: var(--ink-900); }
    header .badge { font-size: 11px; padding: 2px 8px; background: var(--accent); color: #fff; border-radius: 10px; }
    .header-right { margin-left: auto; display: flex; gap: 12px; align-items: center; }
    #user-email { font-size: 13px; color: var(--ink-500); }"""

new_header = """    header {
      height: 60px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      padding: 0 24px;
      gap: 16px;
      position: sticky;
      top: 0;
      background: rgba(255,255,255,0.85);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      z-index: 100;
      box-shadow: 0 1px 0 var(--border);
    }
    header h1 {
      font-size: 16px;
      font-weight: 700;
      color: var(--ink-900);
      background: var(--gradient-primary);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -0.02em;
    }
    header .badge {
      font-size: 11px;
      padding: 3px 10px;
      background: var(--accent-light);
      color: var(--accent);
      border: 1px solid var(--accent-border);
      border-radius: 20px;
      font-weight: 600;
      letter-spacing: 0.02em;
    }
    .header-right { margin-left: auto; display: flex; gap: 12px; align-items: center; }
    #user-email { font-size: 13px; color: var(--ink-500); font-weight: 500; }"""

html = html.replace(old_header, new_header)

# ── 6. 升级主布局：header gradient hero ─────────────────────────
old_main = """    main { display: grid; grid-template-columns: 1fr 1fr; height: calc(100vh - 56px); }"""
new_main = """    main { display: grid; grid-template-columns: 1fr 1fr; height: calc(100vh - 60px); background: var(--gradient-hero); }"""
html = html.replace(old_main, new_main)

# ── 7. 升级 panel-left ─────────────────────────────────────────
old_panel_left = """    .panel-left { border-right: 1px solid var(--border); display: flex; flex-direction: column; overflow: hidden; background: var(--paper); }"""
new_panel_left = """    .panel-left {
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: rgba(255,255,255,0.7);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
    }"""
html = html.replace(old_panel_left, new_panel_left)

# ── 8. 升级上传区 ──────────────────────────────────────────────
old_upload = """.upload-zone {
      margin: 24px;
      padding: 36px 24px;
      border: 2px dashed var(--border);
      border-radius: var(--radius-lg);
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s, background 0.2s, transform 0.15s, box-shadow 0.15s;
      position: relative;
    }
    .upload-zone:hover, .upload-zone.drag-over {
      border-color: var(--accent);
      background: rgba(37,99,235,0.04);
      transform: translateY(-1px);
      box-shadow: var(--shadow);
    }
    .upload-zone:active { transform: scale(0.99); }
    .upload-zone p { color: var(--ink-500); font-size: 14px; }
    .upload-zone .hint { font-size: 12px; margin-top: 4px; color: var(--ink-400); }"""

new_upload = """.upload-zone {
      margin: 20px;
      padding: 28px 20px;
      border: 1.5px dashed var(--border-2);
      border-radius: var(--radius-lg);
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s, background 0.2s, transform 0.15s, box-shadow 0.15s;
      position: relative;
      background: var(--paper-2);
    }
    .upload-zone:hover, .upload-zone.drag-over {
      border-color: var(--accent);
      background: var(--accent-light);
      border-style: solid;
      transform: translateY(-2px);
      box-shadow: 0 0 0 4px var(--accent-light), var(--shadow);
    }
    .upload-zone:active { transform: scale(0.98); }
    .upload-zone p { color: var(--ink-600); font-size: 13px; font-weight: 500; }
    .upload-zone .hint { font-size: 12px; margin-top: 4px; color: var(--ink-400); }
    .upload-zone .upload-icon {
      width: 40px; height: 40px;
      background: var(--accent-light);
      border-radius: var(--radius-md);
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 12px;
      font-size: 20px;
      border: 1px solid var(--accent-border);
    }"""

html = html.replace(old_upload, new_upload)

# ── 9. 升级文件夹树 ─────────────────────────────────────────────
old_folder_tree = """.folder-tree { border-bottom: 1px solid var(--border); }
    .folder-tree-header { display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; font-size: 11px; font-weight: 600; color: var(--ink-400); text-transform: uppercase; letter-spacing: 0.06em; }
    .folder-tree-header span { display: flex; align-items: center; gap: 4px; }
    .folder-tree-header button { border: none; background: none; cursor: pointer; font-size: 11px; color: var(--accent); font-weight: 600; padding: 2px 6px; border-radius: var(--radius-xs); transition: background 0.15s; }
    .folder-tree-header button:hover { background: var(--accent-light); }"""

new_folder_tree = """.folder-tree { border-bottom: 1px solid var(--border); }
    .folder-tree-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px 10px; font-size: 11px; font-weight: 700; color: var(--ink-400); text-transform: uppercase; letter-spacing: 0.08em; }
    .folder-tree-header span { display: flex; align-items: center; gap: 6px; }
    .folder-tree-header button { border: none; background: none; cursor: pointer; font-size: 11px; color: var(--accent); font-weight: 600; padding: 3px 8px; border-radius: var(--radius-sm); transition: background 0.15s, color 0.15s; }
    .folder-tree-header button:hover { background: var(--accent-light); color: var(--accent-hover); }"""

html = html.replace(old_folder_tree, new_folder_tree)

# ── 10. 升级 paper-list 和 papers-container ─────────────────────
old_paper_list = """.paper-list { flex: 1; overflow-y: auto; padding: 16px 20px; }
    .paper-list h3 { font-size: 12px; font-weight: 600; color: var(--ink-400); margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }"""

new_paper_list = """.paper-list { flex: 1; overflow-y: auto; padding: 12px 16px 20px; }
    .paper-list h3 { font-size: 12px; font-weight: 700; color: var(--ink-400); margin-bottom: 10px; display: flex; align-items: center; gap: 6px; text-transform: uppercase; letter-spacing: 0.06em; }"""

html = html.replace(old_paper_list, new_paper_list)

# ── 11. 升级论文卡片 ────────────────────────────────────────────
old_paper_card_css = """.paper-card { border: 1px solid var(--border); border-radius: var(--radius-md); padding: 12px 14px; margin-bottom: 8px; cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s, transform 0.12s; position: relative; background: var(--paper); overflow: hidden; }
    .paper-card:hover { border-color: var(--accent); box-shadow: var(--shadow-hover); transform: translateY(-1px); }
    .paper-card.selected { border-color: var(--accent); background: var(--accent-light); }
    .paper-card-header { display: flex; align-items: flex-start; gap: 8px; }
    .paper-card-title { font-size: 13px; font-weight: 500; color: var(--ink-900); line-height: 1.45; margin-bottom: 4px; }
    .paper-card-meta { font-size: 11px; color: var(--ink-400); line-height: 1.4; }
    .paper-card-status { position: absolute; top: 10px; right: 10px; width: 7px; height: 7px; border-radius: 50%; }
    .status-ready { background: var(--success); box-shadow: 0 0 0 2px rgba(5,150,105,0.2); }
    .status-processing, .status-pending { background: var(--warning); box-shadow: 0 0 0 2px rgba(217,119,6,0.2); }
    .status-error { background: var(--danger); box-shadow: 0 0 0 2px rgba(220,38,38,0.2); }
    .paper-card-title { font-size: 13px; font-weight: 500; color: var(--ink-900); line-height: 1.45; margin-bottom: 4px; }
    .paper-card-meta { font-size: 11px; color: var(--ink-400); line-height: 1.4; }
    .paper-card-badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; font-weight: 600; margin-right: 4px; }
    .badge-blue { background: rgba(37,99,235,0.1); color: #2563EB; }
    .badge-green { background: rgba(5,150,105,0.1); color: #059669; }
    .badge-orange { background: rgba(217,119,6,0.1); color: #D97706; }
    .badge-red { background: rgba(220,38,38,0.1); color: #DC2626; }
    .paper-card-error { font-size: 11px; color: var(--danger); margin-top: 4px; }
    .paper-card-actions { display: flex; gap: 6px; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--border); }
    .paper-card-actions button { border: 1px solid var(--border); background: none; padding: 3px 8px; border-radius: var(--radius-xs); font-size: 11px; cursor: pointer; color: var(--ink-500); transition: all 0.12s; }
    .paper-card-actions button:hover { border-color: var(--danger); color: var(--danger); background: rgba(220,38,38,0.06); }
    .paper-card-checkbox { width: 16px; height: 16px; border: 1.5px solid var(--border-2); border-radius: 4px; flex-shrink: 0; margin-top: 2px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.12s; background: white; }
    .paper-card-checkbox.checked { background: var(--accent); border-color: var(--accent); }
    .paper-card-checkbox.checked::after { content: '✓'; color: white; font-size: 10px; font-weight: 700; }"""

new_paper_card_css = """.paper-card {
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 14px 16px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s, background 0.2s;
      position: relative;
      background: var(--paper);
      overflow: hidden;
      animation: cardIn 0.3s ease both;
    }
    @keyframes cardIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .paper-card:hover {
      border-color: var(--accent-border);
      box-shadow: var(--shadow-hover);
      transform: translateY(-2px);
      background: linear-gradient(135deg, rgba(79,70,229,0.02) 0%, rgba(124,58,237,0.04) 100%);
    }
    .paper-card.selected {
      border-color: var(--accent);
      background: var(--accent-light);
      box-shadow: 0 0 0 3px var(--accent-light), var(--shadow-hover);
    }
    .paper-card-header { display: flex; align-items: flex-start; gap: 10px; }
    .paper-card-title { font-size: 13.5px; font-weight: 600; color: var(--ink-900); line-height: 1.5; margin-bottom: 5px; letter-spacing: -0.01em; }
    .paper-card-meta { font-size: 12px; color: var(--ink-500); line-height: 1.5; }
    .paper-card-status { position: absolute; top: 12px; right: 12px; width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .status-ready { background: var(--success); box-shadow: 0 0 0 3px rgba(5,150,105,0.15); }
    .status-processing, .status-pending { background: var(--warning); box-shadow: 0 0 0 3px rgba(217,119,6,0.15); animation: pulse 2s infinite; }
    .status-error { background: var(--danger); box-shadow: 0 0 0 3px rgba(220,38,38,0.15); }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.5; }
    }
    .paper-card-badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 600; margin-right: 5px; letter-spacing: 0.01em; }
    .badge-blue { background: rgba(37,99,235,0.1); color: #2563EB; }
    .badge-green { background: var(--success-bg); color: var(--success); }
    .badge-orange { background: var(--warning-bg); color: var(--warning); }
    .badge-red { background: var(--danger-bg); color: var(--danger); }
    .paper-card-error { font-size: 12px; color: var(--danger); margin-top: 5px; font-weight: 500; }
    .paper-card-actions { display: flex; gap: 6px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border); }
    .paper-card-actions button { border: 1px solid var(--border); background: none; padding: 4px 10px; border-radius: var(--radius-sm); font-size: 12px; cursor: pointer; color: var(--ink-600); transition: all 0.15s; font-weight: 500; }
    .paper-card-actions button:hover { border-color: var(--danger); color: var(--danger); background: var(--danger-bg); }
    .paper-card-checkbox {
      width: 18px; height: 18px;
      border: 2px solid var(--border-2);
      border-radius: 5px;
      flex-shrink: 0;
      margin-top: 1px;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: all 0.15s;
      background: white;
    }
    .paper-card-checkbox.checked {
      background: var(--accent);
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-light);
    }
    .paper-card-checkbox.checked::after {
      content: '✓'; color: white; font-size: 11px; font-weight: 700;
    }"""

html = html.replace(old_paper_card_css, new_paper_card_css)

# ── 12. 升级 Chat 区域 ──────────────────────────────────────────
old_chat_header = """.quota-banner { padding: 10px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; background: var(--paper); font-size: 12px; color: var(--ink-500); }
    .quota-banner .plan { font-weight: 600; color: var(--ink-700); }
    .quota-banner .papers { font-weight: 500; }
    .chat-messages { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }"""

new_chat_header = """.quota-banner {
      padding: 10px 20px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: rgba(255,255,255,0.8);
      backdrop-filter: blur(8px);
      font-size: 12px;
      color: var(--ink-500);
      font-weight: 500;
    }
    .quota-banner .plan {
      font-weight: 700;
      color: var(--ink-800);
      background: var(--gradient-primary);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .quota-banner .papers { font-weight: 600; color: var(--ink-600); }
    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      scroll-behavior: smooth;
    }"""

html = html.replace(old_chat_header, new_chat_header)

# ── 13. 升级消息气泡 ────────────────────────────────────────────
old_bubble = """.msg { display: flex; flex-direction: column; max-width: 85%; animation: msgIn 0.3s ease both; }
    @keyframes msgIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    .msg.user { align-self: flex-end; align-items: flex-end; }
    .msg.assistant { align-self: flex-start; align-items: flex-start; }
    .bubble {
      padding: 12px 16px;
      border-radius: 14px;
      font-size: 14px;
      line-height: 1.6;
      word-break: break-word;
    }
    .msg.assistant .bubble {
      background: var(--paper);
      border: 1px solid var(--border);
      border-bottom-left-radius: 4px;
      box-shadow: var(--shadow);
      color: var(--ink-700);
    }
    .msg.user .bubble {
      background: var(--accent);
      color: #fff;
      border-bottom-right-radius: 4px;
      box-shadow: 0 2px 8px rgba(37,99,235,0.25);
    }
    .msg-avatar { width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; margin-bottom: 4px; flex-shrink: 0; }
    .msg.assistant .msg-avatar { background: var(--gradient-primary); color: #fff; }
    .msg.user .msg-avatar { background: rgba(37,99,235,0.15); color: var(--accent); }
    .answer-icon { margin-left: 6px; opacity: 0.4; font-size: 12px; }
    .thinking-block {
      background: var(--paper-3);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 12px 14px;
      margin-bottom: 8px;
      font-size: 13px;
      color: var(--ink-500);
      cursor: pointer;
      transition: background 0.15s;
    }
    .thinking-block:hover { background: var(--border); }
    .thinking-block summary { font-weight: 600; color: var(--ink-700); cursor: pointer; user-select: none; list-style: none; display: flex; align-items: center; gap: 6px; }
    .thinking-block summary::before { content: '🤔'; }
    .thinking-block summary::marker { display: none; }
    .thinking-content { margin-top: 8px; color: var(--ink-600); line-height: 1.6; }"""

new_bubble = """.msg {
      display: flex;
      flex-direction: column;
      max-width: 80%;
      animation: msgIn 0.35s cubic-bezier(0.34,1.2,0.64,1) both;
    }
    @keyframes msgIn {
      from { opacity: 0; transform: translateY(12px) scale(0.97); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    .msg.user { align-self: flex-end; align-items: flex-end; }
    .msg.assistant { align-self: flex-start; align-items: flex-start; }
    .bubble {
      padding: 14px 18px;
      border-radius: var(--radius-lg);
      font-size: 14px;
      line-height: 1.7;
      word-break: break-word;
    }
    .msg.assistant .bubble {
      background: var(--paper);
      border: 1px solid var(--border);
      border-bottom-left-radius: var(--radius-xs);
      box-shadow: var(--shadow);
      color: var(--ink-700);
      border-top-left-radius: var(--radius-xs);
    }
    .msg.user .bubble {
      background: var(--gradient-primary);
      color: #fff;
      border-bottom-right-radius: var(--radius-xs);
      box-shadow: 0 4px 16px rgba(79,70,229,0.3);
      border-top-right-radius: var(--radius-xs);
    }
    .msg-avatar {
      width: 30px; height: 30px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 13px;
      margin-bottom: 6px;
      flex-shrink: 0;
      box-shadow: var(--shadow);
    }
    .msg.assistant .msg-avatar {
      background: var(--gradient-primary);
      color: #fff;
    }
    .msg.user .msg-avatar {
      background: rgba(79,70,229,0.15);
      color: var(--accent);
      display: none; /* 隐藏 AI 头像，节省空间 */
    }
    .answer-icon { margin-left: 6px; opacity: 0.5; font-size: 12px; }
    .thinking-block {
      background: var(--paper-3);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 12px 16px;
      margin-bottom: 8px;
      font-size: 13px;
      color: var(--ink-500);
      cursor: pointer;
      transition: background 0.15s, box-shadow 0.15s;
    }
    .thinking-block:hover {
      background: var(--border);
      box-shadow: var(--shadow);
    }
    .thinking-block summary {
      font-weight: 600;
      color: var(--ink-600);
      cursor: pointer;
      user-select: none;
      list-style: none;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .thinking-block summary::before { content: ''; }
    .thinking-block summary::marker { display: none; }
    .thinking-content {
      margin-top: 10px;
      color: var(--ink-600);
      line-height: 1.65;
      border-top: 1px solid var(--border);
      padding-top: 10px;
    }"""

html = html.replace(old_bubble, new_bubble)

# ── 14. 升级 chat-input-area ────────────────────────────────────
old_chat_input = """.chat-input-area { padding: 14px 20px 20px; border-top: 1px solid var(--border); background: rgba(255,255,255,0.9); backdrop-filter: blur(8px); }
    .chat-input-row { display: flex; align-items: flex-end; gap: 10px; border: 1.5px solid var(--border); border-radius: var(--radius-lg); padding: 6px 6px 6px 14px; background: var(--paper); transition: border-color 0.2s, box-shadow 0.2s; }
    .chat-input-row:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-light); }
    .chat-input-row textarea { flex: 1; border: none; outline: none; resize: none; font-size: 14px; line-height: 1.5; color: var(--ink-700); background: transparent; min-height: 24px; max-height: 120px; font-family: inherit; }
    .chat-input-row textarea::placeholder { color: var(--ink-400); }
    .btn-send { width: 36px; height: 36px; border: none; border-radius: var(--radius-sm); background: var(--accent); color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.15s, transform 0.1s, box-shadow 0.15s; flex-shrink: 0; }
    .btn-send:hover { background: var(--accent-hover); box-shadow: 0 4px 12px rgba(37,99,235,0.3); transform: scale(1.05); }
    .btn-send:active { transform: scale(0.95); }
    .btn-send:disabled { background: var(--ink-300); cursor: not-allowed; transform: none; box-shadow: none; }
    .btn-send .btn-icon { font-size: 16px; font-weight: 700; line-height: 1; }
    .btn-send .spinner { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff; border-radius: 50%; animation: spin 0.7s linear infinite; display: none; }
    .btn-send.loading .btn-icon { display: none; }
    .btn-send.loading .spinner { display: block; }
    @keyframes spin { to { transform: rotate(360deg); } }"""

new_chat_input = """.chat-input-area {
      padding: 14px 20px 20px;
      border-top: 1px solid var(--border);
      background: rgba(255,255,255,0.9);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }
    .chat-input-row {
      display: flex;
      align-items: flex-end;
      gap: 10px;
      border: 1.5px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 6px 6px 6px 16px;
      background: var(--paper);
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .chat-input-row:focus-within {
      border-color: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-light), var(--shadow);
    }
    .chat-input-row textarea {
      flex: 1;
      border: none;
      outline: none;
      resize: none;
      font-size: 14px;
      line-height: 1.6;
      color: var(--ink-700);
      background: transparent;
      min-height: 26px;
      max-height: 140px;
      font-family: inherit;
    }
    .chat-input-row textarea::placeholder { color: var(--ink-400); }
    .btn-send {
      width: 40px; height: 40px;
      border: none;
      border-radius: var(--radius-md);
      background: var(--gradient-primary);
      color: #fff;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: transform 0.1s, box-shadow 0.15s, opacity 0.15s;
      flex-shrink: 0;
      box-shadow: 0 2px 8px rgba(79,70,229,0.25);
    }
    .btn-send:hover {
      box-shadow: 0 4px 16px rgba(79,70,229,0.4);
      transform: scale(1.05);
    }
    .btn-send:active { transform: scale(0.95); }
    .btn-send:disabled {
      background: var(--ink-300);
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
      opacity: 0.7;
    }
    .btn-send .btn-icon { font-size: 18px; font-weight: 700; line-height: 1; }
    .btn-send .spinner {
      width: 18px; height: 18px;
      border: 2.5px solid rgba(255,255,255,0.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      display: none;
    }
    .btn-send.loading .btn-icon { display: none; }
    .btn-send.loading .spinner { display: block; }
    @keyframes spin { to { transform: rotate(360deg); } }"""

html = html.replace(old_chat_input, new_chat_input)

# ── 15. 升级 Chat 模式切换按钮 ──────────────────────────────────
old_mode_btn = """.chat-mode-row { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
    .mode-btn { border: 1px solid var(--border); background: none; padding: 5px 12px; border-radius: 20px; font-size: 12px; cursor: pointer; color: var(--ink-500); transition: all 0.15s; font-weight: 500; }
    .mode-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-light); }
    .mode-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }"""

new_mode_btn = """.chat-mode-row { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
    .mode-btn {
      border: 1px solid var(--border);
      background: var(--paper);
      padding: 5px 14px;
      border-radius: 20px;
      font-size: 12px;
      cursor: pointer;
      color: var(--ink-600);
      transition: all 0.15s;
      font-weight: 500;
      letter-spacing: 0.01em;
    }
    .mode-btn:hover {
      border-color: var(--accent-border);
      color: var(--accent);
      background: var(--accent-light);
    }
    .mode-btn.active {
      background: var(--gradient-primary);
      border-color: transparent;
      color: #fff;
      box-shadow: 0 2px 8px rgba(79,70,229,0.25);
    }"""

html = html.replace(old_mode_btn, new_mode_btn)

# ── 16. 升级 Auth Screen ─────────────────────────────────────────
old_auth = """    #auth-screen {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--gradient-hero, linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%));
      padding: 20px;
    }
    .auth-card {
      background: var(--paper);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 36px 32px;
      width: 100%;
      max-width: 400px;
      box-shadow: var(--shadow-lg);
    }
    .auth-card h2 { font-size: 22px; font-weight: 700; color: var(--ink-900); margin-bottom: 6px; text-align: center; }
    .auth-card p { font-size: 14px; color: var(--ink-500); text-align: center; margin-bottom: 24px; }
    .auth-card input {
      width: 100%;
      padding: 10px 14px;
      border: 1.5px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
      background: var(--paper);
      color: var(--ink-700);
      margin-bottom: 12px;
    }
    .auth-card input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-light); }
    .auth-card input::placeholder { color: var(--ink-400); }
    .btn-login { width: 100%; padding: 11px; background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.15s, transform 0.1s; margin-top: 4px; }
    .btn-login:hover { background: var(--accent-hover); transform: translateY(-1px); }
    .btn-login:active { transform: scale(0.99); }
    .btn-login:disabled { background: var(--ink-300); cursor: not-allowed; transform: none; }
    .auth-switch { text-align: center; margin-top: 16px; font-size: 13px; color: var(--ink-500); }
    .auth-switch a { color: var(--accent); text-decoration: none; font-weight: 500; cursor: pointer; }
    .auth-switch a:hover { text-decoration: underline; }
    #auth-error { color: var(--danger); font-size: 13px; text-align: center; margin-bottom: 12px; min-height: 20px; }"""

new_auth = """    #auth-screen {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--gradient-hero);
      padding: 20px;
    }
    .auth-card {
      background: var(--paper);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 40px 36px;
      width: 100%;
      max-width: 420px;
      box-shadow: var(--shadow-xl);
      animation: authIn 0.4s cubic-bezier(0.34,1.2,0.64,1) both;
    }
    @keyframes authIn {
      from { opacity: 0; transform: translateY(20px) scale(0.97); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    .auth-card h2 {
      font-size: 24px;
      font-weight: 700;
      color: var(--ink-900);
      margin-bottom: 8px;
      text-align: center;
      letter-spacing: -0.03em;
    }
    .auth-card p {
      font-size: 14px;
      color: var(--ink-500);
      text-align: center;
      margin-bottom: 28px;
      line-height: 1.6;
    }
    .auth-card .input-wrap { position: relative; margin-bottom: 14px; }
    .auth-card input {
      width: 100%;
      padding: 12px 16px;
      border: 1.5px solid var(--border);
      border-radius: var(--radius-md);
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
      background: var(--paper-2);
      color: var(--ink-700);
      font-family: inherit;
    }
    .auth-card input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-light);
      background: var(--paper);
    }
    .auth-card input::placeholder { color: var(--ink-400); }
    .btn-login {
      width: 100%;
      padding: 13px;
      background: var(--gradient-primary);
      color: #fff;
      border: none;
      border-radius: var(--radius-md);
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.1s, box-shadow 0.15s, opacity 0.15s;
      margin-top: 4px;
      letter-spacing: 0.01em;
      box-shadow: 0 2px 8px rgba(79,70,229,0.25);
    }
    .btn-login:hover {
      box-shadow: 0 4px 20px rgba(79,70,229,0.4);
      transform: translateY(-1px);
    }
    .btn-login:active { transform: scale(0.99); }
    .btn-login:disabled {
      opacity: 0.6;
      cursor: not-allowed;
      transform: none;
      box-shadow: none;
    }
    .auth-switch {
      text-align: center;
      margin-top: 18px;
      font-size: 13px;
      color: var(--ink-500);
    }
    .auth-switch a { color: var(--accent); text-decoration: none; font-weight: 600; cursor: pointer; }
    .auth-switch a:hover { text-decoration: underline; }
    #auth-error {
      color: var(--danger);
      font-size: 13px;
      text-align: center;
      margin-bottom: 14px;
      min-height: 20px;
      font-weight: 500;
      background: var(--danger-bg);
      padding: 8px 12px;
      border-radius: var(--radius-sm);
      border: 1px solid rgba(220,38,38,0.15);
    }"""

html = html.replace(old_auth, new_auth)

# ── 17. 升级 Modal ────────────────────────────────────────────────
old_modal = """.modal-card { background: var(--paper); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 24px; width: 380px; max-width: 90vw; box-shadow: var(--shadow-lg); }
    .modal-card h3 { font-size: 16px; font-weight: 600; color: var(--ink-900); margin-bottom: 16px; }
    .modal-card input, .modal-card select { width: 100%; padding: 9px 12px; border: 1.5px solid var(--border); border-radius: var(--radius-sm); font-size: 14px; outline: none; transition: border-color 0.2s; background: var(--paper); color: var(--ink-700); margin-bottom: 10px; }
    .modal-card input:focus, .modal-card select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-light); }
    .btn-row { display: flex; gap: 8px; justify-content: flex-end; }
    .btn-cancel { padding: 8px 16px; border: 1px solid var(--border); background: none; border-radius: var(--radius-sm); font-size: 13px; cursor: pointer; color: var(--ink-600); }
    .btn-cancel:hover { background: var(--paper-3); }
    .btn-confirm { padding: 8px 16px; border: none; background: var(--accent); color: #fff; border-radius: var(--radius-sm); font-size: 13px; font-weight: 600; cursor: pointer; }
    .btn-confirm:hover { background: var(--accent-hover); }"""

new_modal = """.modal-card {
      background: var(--paper);
      border: 1px solid var(--border);
      border-radius: var(--radius-xl);
      padding: 28px;
      width: 420px;
      max-width: 90vw;
      box-shadow: var(--shadow-xl);
      animation: modalIn 0.3s cubic-bezier(0.34,1.3,0.64,1) both;
    }
    @keyframes modalIn {
      from { opacity: 0; transform: scale(0.95) translateY(-10px); }
      to { opacity: 1; transform: scale(1) translateY(0); }
    }
    .modal-card h3 {
      font-size: 17px;
      font-weight: 700;
      color: var(--ink-900);
      margin-bottom: 16px;
      letter-spacing: -0.02em;
    }
    .modal-card input, .modal-card select {
      width: 100%;
      padding: 10px 14px;
      border: 1.5px solid var(--border);
      border-radius: var(--radius-md);
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
      background: var(--paper-2);
      color: var(--ink-700);
      margin-bottom: 12px;
      font-family: inherit;
    }
    .modal-card input:focus, .modal-card select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-light);
      background: var(--paper);
    }
    .btn-row { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }
    .btn-cancel {
      padding: 9px 18px;
      border: 1px solid var(--border);
      background: none;
      border-radius: var(--radius-md);
      font-size: 13px;
      cursor: pointer;
      color: var(--ink-600);
      font-weight: 500;
      font-family: inherit;
      transition: all 0.15s;
    }
    .btn-cancel:hover { background: var(--paper-3); border-color: var(--border-2); }
    .btn-confirm {
      padding: 9px 18px;
      border: none;
      background: var(--gradient-primary);
      color: #fff;
      border-radius: var(--radius-md);
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 2px 8px rgba(79,70,229,0.25);
      transition: all 0.15s;
      font-family: inherit;
    }
    .btn-confirm:hover {
      box-shadow: 0 4px 16px rgba(79,70,229,0.4);
      transform: translateY(-1px);
    }"""

html = html.replace(old_modal, new_modal)

# ── 18. 升级文件夹列表项 ────────────────────────────────────────
old_folder_item = """.folder-item { display: flex; align-items: center; padding: 7px 20px; cursor: pointer; font-size: 13px; color: var(--ink-600); border-radius: 0; transition: background 0.12s, color 0.12s; gap: 6px; position: relative; }
    .folder-item:hover { background: var(--paper-3); color: var(--ink-700); }
    .folder-item.active { background: var(--accent-light); color: var(--accent); font-weight: 600; }
    .folder-item.active::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--accent); border-radius: 0 2px 2px 0; }"""

new_folder_item = """.folder-item {
      display: flex;
      align-items: center;
      padding: 8px 20px;
      cursor: pointer;
      font-size: 13px;
      color: var(--ink-600);
      border-radius: 0;
      transition: background 0.15s, color 0.15s;
      gap: 8px;
      position: relative;
      font-weight: 500;
    }
    .folder-item:hover { background: var(--accent-light); color: var(--ink-700); }
    .folder-item.active {
      background: var(--accent-light);
      color: var(--accent);
      font-weight: 700;
    }
    .folder-item.active::before {
      content: '';
      position: absolute;
      left: 0; top: 4px; bottom: 4px;
      width: 3px;
      background: var(--accent);
      border-radius: 0 3px 3px 0;
    }"""

html = html.replace(old_folder_item, new_folder_item)

# ── 19. 升级进度条 ──────────────────────────────────────────────
old_progress = """.progress-bar-wrap { height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; }
    .progress-bar-fill { height: 100%; background: var(--accent); border-radius: 2px; transition: width 0.3s ease; width: 0; }"""

new_progress = """.progress-bar-wrap {
      height: 4px;
      background: var(--border);
      border-radius: 3px;
      overflow: hidden;
    }
    .progress-bar-fill {
      height: 100%;
      background: var(--gradient-primary);
      border-radius: 3px;
      transition: width 0.3s ease;
      width: 0;
      box-shadow: 0 0 8px rgba(79,70,229,0.4);
    }"""

html = html.replace(old_progress, new_progress)

# ── 20. 升级 error-msg ──────────────────────────────────────────
old_err = """.error-msg { font-size: 12px; color: var(--danger); margin-top: 6px; min-height: 18px; }
    .chat-error { font-size: 13px; color: var(--danger); padding: 8px 14px; background: rgba(220,38,38,0.08); border: 1px solid rgba(220,38,38,0.2); border-radius: var(--radius-sm); margin: 8px 20px; }"""

new_err = """.error-msg { font-size: 12px; color: var(--danger); margin-top: 6px; min-height: 18px; font-weight: 500; }
    .chat-error {
      font-size: 13px;
      color: var(--danger);
      padding: 10px 16px;
      background: var(--danger-bg);
      border: 1px solid rgba(220,38,38,0.15);
      border-radius: var(--radius-md);
      margin: 8px 20px;
      font-weight: 500;
    }"""

html = html.replace(old_err, new_err)

# ── 21. 添加批量移动按钮新样式 ──────────────────────────────────
old_batch = """.batch-move-hint { font-size: 13px; color: var(--ink-500); margin: 0; }
    #batch-move-modal-overlay, #new-folder-modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
    #batch-move-modal-overlay.hidden, #new-folder-modal-overlay.hidden { display: none; }
    #batch-move-modal-overlay > div, #new-folder-modal-overlay > div { animation: modalIn 0.2s ease; }
    @keyframes modalIn { from { opacity: 0; transform: scale(0.96); } to { opacity: 1; transform: scale(1); } }"""

new_batch = """.batch-move-hint { font-size: 13px; color: var(--ink-500); margin: 0 0 4px; font-weight: 500; }
    #batch-move-modal-overlay, #new-folder-modal-overlay {
      position: fixed; inset: 0;
      background: rgba(15,23,42,0.6);
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      display: flex; align-items: center; justify-content: center;
      z-index: 1000;
    }
    #batch-move-modal-overlay.hidden, #new-folder-modal-overlay.hidden { display: none; }"""

html = html.replace(old_batch, new_batch)

# ── 22. 升级引用列表样式（答案中的引用）────────────────────────
old_citation = """.citation-list { margin-top: 10px; border-top: 1px solid var(--border); padding-top: 10px; }
    .citation-list p { font-size: 12px; color: var(--ink-400); font-weight: 600; margin-bottom: 6px; }
    .citation-item { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: 12px; color: var(--ink-600); }
    .citation-item:last-child { border-bottom: none; }
    .citation-num { color: var(--accent); font-weight: 700; flex-shrink: 0; min-width: 20px; }
    .citation-text { flex: 1; line-height: 1.5; }"""

new_citation = """.citation-list { margin-top: 12px; border-top: 1px solid var(--border); padding-top: 12px; }
    .citation-list p { font-size: 11px; color: var(--ink-400); font-weight: 700; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.06em; }
    .citation-item {
      display: flex; align-items: flex-start; gap: 10px;
      padding: 6px 0;
      border-bottom: 1px solid var(--border);
      font-size: 12.5px;
      color: var(--ink-600);
      line-height: 1.5;
    }
    .citation-item:last-child { border-bottom: none; }
    .citation-num {
      color: var(--accent);
      font-weight: 700;
      flex-shrink: 0;
      min-width: 22px;
      background: var(--accent-light);
      padding: 1px 6px;
      border-radius: 10px;
      font-size: 11px;
      text-align: center;
    }
    .citation-text { flex: 1; }"""

html = html.replace(old_citation, new_citation)

# ── 23. 质量警告样式升级 ────────────────────────────────────────
old_qwarn = """.quality-warning { font-size: 12px; color: var(--warning); background: rgba(217,119,6,0.08); border: 1px solid rgba(217,119,6,0.2); border-radius: var(--radius-sm); padding: 8px 12px; margin: 8px 0; }"""

new_qwarn = """.quality-warning {
      font-size: 12px;
      color: var(--warning);
      background: var(--warning-bg);
      border: 1px solid rgba(217,119,6,0.2);
      border-radius: var(--radius-md);
      padding: 10px 14px;
      margin: 10px 0;
      font-weight: 500;
    }"""

html = html.replace(old_qwarn, new_qwarn)

# ── 24. 滚动条美化 ──────────────────────────────────────────────
old_scrollbar = """    /* ── Scrollbar ──────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border-2, #cbd5e1); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--ink-400); }"""

new_scrollbar = """    /* ── Scrollbar ──────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--ink-300); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--ink-400); }"""

html = html.replace(old_scrollbar, new_scrollbar)

# ── 25. 升级 chat-messages 内的引用块 ─────────────────────────
# 找到 citation-list 相关样式（chat-messages 内的）
old_cite2 = """.chat-messages .citation-list { border-top: 1px solid var(--border); padding-top: 10px; margin-top: 10px; }
    .chat-messages .citation-list p { font-size: 11px; color: var(--ink-400); font-weight: 600; margin-bottom: 6px; }
    .chat-messages .citation-item { display: flex; align-items: flex-start; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--border); font-size: 12px; color: var(--ink-600); }
    .chat-messages .citation-item:last-child { border-bottom: none; }
    .chat-messages .citation-num { color: var(--accent); font-weight: 700; flex-shrink: 0; min-width: 20px; }"""

new_cite2 = """.chat-messages .citation-list { border-top: 1px solid var(--border); padding-top: 12px; margin-top: 12px; }
    .chat-messages .citation-list p { font-size: 11px; color: var(--ink-400); font-weight: 700; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.06em; }
    .chat-messages .citation-item { display: flex; align-items: flex-start; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 12.5px; color: var(--ink-600); line-height: 1.5; }
    .chat-messages .citation-item:last-child { border-bottom: none; }
    .chat-messages .citation-num {
      color: var(--accent);
      font-weight: 700;
      flex-shrink: 0;
      min-width: 22px;
      background: var(--accent-light);
      padding: 1px 6px;
      border-radius: 10px;
      font-size: 11px;
      text-align: center;
    }"""

html = html.replace(old_cite2, new_cite2)

# ── 26. 升级 panel-right ────────────────────────────────────────
old_panel_right = """.panel-right { display: flex; flex-direction: column; overflow: hidden; }"""
new_panel_right = """.panel-right {
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: rgba(255,255,255,0.5);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
    }"""
html = html.replace(old_panel_right, new_panel_right)

# ── 27. 升级 upload-zone hover icon ──────────────────────────────
old_upload_icon = """.upload-zone:hover .upload-zone-text { color: var(--accent); }
    .upload-zone.drag-over .upload-zone-text { color: var(--accent); }"""
new_upload_icon = """.upload-zone:hover .upload-zone-text { color: var(--accent); font-weight: 600; }
    .upload-zone.drag-over .upload-zone-text { color: var(--accent); font-weight: 600; }"""
html = html.replace(old_upload_icon, new_upload_icon)

# ── 28. 升级 spinner ─────────────────────────────────────────────
old_spinner = """.upload-spinner { width: 20px; height: 20px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; margin: 0 auto 8px; }
    .upload-zone.uploading .upload-spinner { border-top-color: var(--success); }"""

new_spinner = """.upload-spinner { width: 20px; height: 20px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.7s linear infinite; margin: 0 auto 8px; }
    .upload-zone.uploading .upload-spinner { border-top-color: var(--success); }"""
# keep same

# ── 29. Save ────────────────────────────────────────────────────
with open('/root/.openclaw/workspace/rag-knowledge-base/phase0/frontend/index.html', 'w') as f:
    f.write(html)

print("✅ CSS upgrade complete!")
print(f"File size: {len(html)} bytes")
