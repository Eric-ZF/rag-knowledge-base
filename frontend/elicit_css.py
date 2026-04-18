#!/usr/bin/env python3
"""Elicit-style CSS redesign — clean, professional, information-dense"""
import re

with open('/var/www/rag/index.html') as f:
    html = f.read()

print(f"Original size: {len(html)}")

# ── 1. Replace CSS variables ─────────────────────────────────────
old_vars = """      /* ─── Elicit 学术风格色板 ─────────────────────────── */
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
    }"""

new_vars = """      /* ─── Elicit 克制专业风格色板 ─────────────────────── */
      --ink-900: #111827;
      --ink-800: #1f2937;
      --ink-700: #374151;
      --ink-600: #4b5563;
      --ink-500: #6b7280;
      --ink-400: #9ca3af;
      --ink-300: #d1d5db;
      --paper:   #ffffff;
      --paper-2: #f9fafb;
      --paper-3: #f3f4f6;
      --accent:  #2563eb;          /* 学术蓝 */
      --accent-hover: #1d4ed8;
      --accent-light: rgba(37,99,235,0.06);
      --accent-border: rgba(37,99,235,0.15);
      --success: #059669;
      --success-bg: rgba(5,150,105,0.07);
      --danger:  #dc2626;
      --danger-bg: rgba(220,38,38,0.07);
      --warning: #d97706;
      --warning-bg: rgba(217,119,6,0.07);
      --info:    #0284c7;
      --info-bg: rgba(2,132,199,0.07);
      --gradient-primary: #2563eb;
      --border:  #e5e7eb;
      --border-2: #d1d5db;
      --shadow:  0 1px 2px rgba(0,0,0,0.05);
      --shadow-hover: 0 2px 8px rgba(0,0,0,0.08);
      --shadow-lg: 0 4px 16px rgba(0,0,0,0.1);
      --shadow-xl: 0 8px 32px rgba(0,0,0,0.12);
      --radius-xs: 3px;
      --radius-sm: 5px;
      --radius-md: 8px;
      --radius-lg: 10px;
    }"""
html = html.replace(old_vars, new_vars)

# ── 2. Dark mode ──────────────────────────────────────────────
old_dark = """    @media (prefers-color-scheme: dark) {
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
    }"""

new_dark = """    @media (prefers-color-scheme: dark) {
      :root {
        --ink-900: #f9fafb;
        --ink-800: #e5e7eb;
        --ink-700: #d1d5db;
        --ink-600: #9ca3af;
        --ink-500: #6b7280;
        --ink-400: #4b5563;
        --ink-300: #374151;
        --paper:   #111827;
        --paper-2: #1f2937;
        --paper-3: #1f2937;
        --accent:  #60a5fa;
        --accent-hover: #93c5fd;
        --accent-light: rgba(96,165,250,0.08);
        --accent-border: rgba(96,165,250,0.2);
        --success-bg: rgba(5,150,105,0.1);
        --danger-bg: rgba(220,38,38,0.1);
        --warning-bg: rgba(217,119,6,0.1);
        --info-bg: rgba(56,189,248,0.1);
        --gradient-primary: #60a5fa;
        --border:  #374151;
        --border-2: #4b5563;
        --shadow:  0 1px 2px rgba(0,0,0,0.3);
        --shadow-hover: 0 2px 8px rgba(0,0,0,0.35);
        --shadow-lg: 0 4px 16px rgba(0,0,0,0.4);
        --shadow-xl: 0 8px 32px rgba(0,0,0,0.5);
      }
    }"""
html = html.replace(old_dark, new_dark)

# ── 3. Body background → pure white ────────────────────────────
html = html.replace('background: var(--paper-2);', 'background: var(--paper);')

# ── 4. Header: simple white, no blur ─────────────────────────
old_header = """    header {
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
    }"""

new_header = """    header {
      height: 52px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      padding: 0 20px;
      gap: 12px;
      position: sticky;
      top: 0;
      background: var(--paper);
      z-index: 100;
    }
    header h1 {
      font-size: 15px;
      font-weight: 700;
      color: var(--ink-900);
      letter-spacing: -0.01em;
    }
    header .badge {
      font-size: 11px;
      padding: 2px 8px;
      background: var(--accent-light);
      color: var(--accent);
      border: 1px solid var(--accent-border);
      border-radius: 10px;
      font-weight: 600;
    }"""
html = html.replace(old_header, new_header)

# ── 5. Main layout: simple white ────────────────────────────────
old_main = """    main { display: grid; grid-template-columns: 1fr 1fr; height: calc(100vh - 60px); background: var(--gradient-hero); }"""
new_main = """    main { display: grid; grid-template-columns: 1fr 1fr; height: calc(100vh - 52px); }"""
html = html.replace(old_main, new_main)

# ── 6. Panel left: no blur ────────────────────────────────────
old_panel_left = """    .panel-left {
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: rgba(255,255,255,0.7);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
    }"""
new_panel_left = """    .panel-left {
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: var(--paper);
    }"""
html = html.replace(old_panel_left, new_panel_left)

# ── 7. Panel right: no blur ───────────────────────────────────
old_panel_right = """    .panel-right {
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: rgba(255,255,255,0.5);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
    }"""
new_panel_right = """    .panel-right {
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: var(--paper);
    }"""
html = html.replace(old_panel_right, new_panel_right)

# ── 8. Quota banner: clean white ──────────────────────────────
old_qbanner = """    .quota-banner {
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
    }"""

new_qbanner = """    .quota-banner {
      padding: 8px 20px;
      border-bottom: 1px solid var(--border);
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: var(--paper);
      font-size: 12px;
      color: var(--ink-500);
      font-weight: 500;
    }
    .quota-banner .plan { font-weight: 700; color: var(--accent); }"""
html = html.replace(old_qbanner, new_qbanner)

# ── 9. Paper cards: clean white, subtle ──────────────────────
old_paper = """.paper-item {
      padding: 12px;
      border-radius: var(--radius-md);
      border: 1px solid var(--border);
      margin-bottom: 8px;
      transition: box-shadow 0.18s, transform 0.18s, border-color 0.18s;
      display: flex;
      align-items: flex-start;
      gap: 8px;
    }
    .paper-item:hover {
      box-shadow: var(--shadow-hover);
      transform: translateY(-1px);
      border-color: rgba(37, 99, 235, 0.4);
    }"""

new_paper = """.paper-item {
      padding: 11px 14px;
      border-radius: var(--radius-md);
      border: 1px solid var(--border);
      margin-bottom: 6px;
      transition: box-shadow 0.15s, border-color 0.15s;
      display: flex;
      align-items: flex-start;
      gap: 8px;
      background: var(--paper);
    }
    .paper-item:hover {
      box-shadow: var(--shadow-hover);
      border-color: var(--accent-border);
    }"""
html = html.replace(old_paper, new_paper)

# ── 10. Paper title/meta ──────────────────────────────────────
old_ptitle = """.paper-item .title { font-size: 14px; font-weight: 500; color: var(--ink-900); }"""
new_ptitle = """.paper-item .title { font-size: 13.5px; font-weight: 600; color: var(--ink-900); line-height: 1.4; }"""
html = html.replace(old_ptitle, new_ptitle)

# ── 11. Upload zone: clean ────────────────────────────────────
old_upload = """.upload-zone {
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

new_upload = """.upload-zone {
      margin: 12px 16px;
      padding: 20px;
      border: 1.5px dashed var(--border);
      border-radius: var(--radius-md);
      text-align: center;
      cursor: pointer;
      transition: border-color 0.15s, background 0.15s;
      position: relative;
      background: var(--paper-3);
    }
    .upload-zone:hover, .upload-zone.drag-over {
      border-color: var(--accent);
      background: var(--accent-light);
    }
    .upload-zone p { color: var(--ink-600); font-size: 13px; }
    .upload-zone .hint { font-size: 11px; margin-top: 3px; color: var(--ink-400); }"""
html = html.replace(old_upload, new_upload)

# ── 12. Auth card: clean white, no shadow-xl ──────────────────
old_auth = """    .auth-card {
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
    }"""

new_auth = """    .auth-card {
      background: var(--paper);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 32px 28px;
      width: 100%;
      max-width: 380px;
      box-shadow: var(--shadow-lg);
    }
    .auth-card h2 {
      font-size: 20px;
      font-weight: 700;
      color: var(--ink-900);
      margin-bottom: 4px;
      text-align: center;
    }
    .auth-card p {
      font-size: 13px;
      color: var(--ink-500);
      text-align: center;
      margin-bottom: 20px;
      line-height: 1.5;
    }
    .auth-card input {
      width: 100%;
      padding: 9px 12px;
      border: 1.5px solid var(--border);
      border-radius: var(--radius-sm);
      font-size: 14px;
      outline: none;
      transition: border-color 0.15s;
      background: var(--paper);
      color: var(--ink-700);
      font-family: inherit;
      margin-bottom: 10px;
    }
    .auth-card input:focus { border-color: var(--accent); }
    .auth-card input::placeholder { color: var(--ink-400); }
    .btn-login {
      width: 100%;
      padding: 10px;
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: var(--radius-sm);
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: background 0.15s;
      margin-top: 4px;
    }
    .btn-login:hover { background: var(--accent-hover); }
    .btn-login:active { transform: scale(0.99); }
    .btn-login:disabled { opacity: 0.6; cursor: not-allowed; }"""
html = html.replace(old_auth, new_auth)

# ── 13. Send button: solid accent, clean ─────────────────────
old_send = """.btn-send {
      width: 40px; height: 40px; border-radius: var(--radius-md);
      background: var(--gradient-primary); color: #fff; border: none;
      cursor: pointer; display: flex; align-items: center;
      justify-content: center; font-size: 18px;
      transition: transform 0.1s, box-shadow 0.15s, opacity 0.15s;
      flex-shrink: 0; position: relative;
      box-shadow: 0 2px 8px rgba(79,70,229,0.25);
    }
    .btn-send:hover:not(:disabled) {
      box-shadow: 0 4px 16px rgba(79,70,229,0.4);
      transform: scale(1.05);
    }
    .btn-send:active:not(:disabled) { transform: scale(0.95); }"""

new_send = """.btn-send {
      width: 36px; height: 36px; border-radius: var(--radius-sm);
      background: var(--accent); color: #fff; border: none;
      cursor: pointer; display: flex; align-items: center;
      justify-content: center; font-size: 16px;
      transition: background 0.15s, transform 0.1s;
      flex-shrink: 0; position: relative;
    }
    .btn-send:hover:not(:disabled) { background: var(--accent-hover); transform: scale(1.05); }
    .btn-send:active:not(:disabled) { transform: scale(0.95); }"""
html = html.replace(old_send, new_send)

# ── 14. Chat bubble: clean white ──────────────────────────────
old_bubble = """.msg {
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
    }"""

new_bubble = """.msg {
      display: flex;
      flex-direction: column;
      max-width: 82%;
    }
    .msg.user { align-self: flex-end; align-items: flex-end; }
    .msg.assistant { align-self: flex-start; align-items: flex-start; }
    .bubble {
      padding: 10px 14px;
      border-radius: var(--radius-md);
      font-size: 14px;
      line-height: 1.65;
      word-break: break-word;
    }
    .msg.assistant .bubble {
      background: var(--paper);
      border: 1px solid var(--border);
      border-bottom-left-radius: 2px;
      color: var(--ink-700);
    }
    .msg.user .bubble {
      background: var(--accent);
      color: #fff;
      border-bottom-right-radius: 2px;
    }"""
html = html.replace(old_bubble, new_bubble)

# ── 15. Chat input area: clean white ────────────────────────
old_chat_input = """.chat-input-area {
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
    }"""

new_chat_input = """.chat-input-area {
      padding: 12px 20px 16px;
      border-top: 1px solid var(--border);
      background: var(--paper);
    }
    .chat-input-row {
      display: flex;
      align-items: flex-end;
      gap: 8px;
      border: 1.5px solid var(--border);
      border-radius: var(--radius-md);
      padding: 6px 6px 6px 14px;
      background: var(--paper);
      transition: border-color 0.15s;
    }
    .chat-input-row:focus-within { border-color: var(--accent); }"""
html = html.replace(old_chat_input, new_chat_input)

# ── 16. Mode buttons: clean pill ─────────────────────────────
old_mode = """.chat-mode-row { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }
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

new_mode = """.chat-mode-row { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
    .mode-btn {
      border: 1px solid var(--border);
      background: var(--paper);
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 12px;
      cursor: pointer;
      color: var(--ink-600);
      transition: all 0.12s;
      font-weight: 500;
    }
    .mode-btn:hover { border-color: var(--accent-border); color: var(--accent); background: var(--accent-light); }
    .mode-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; }"""
html = html.replace(old_mode, new_mode)

# ── 17. Folder tree: clean ───────────────────────────────────
old_folder = """.folder-tree { border-bottom: 1px solid var(--border); }
    .folder-tree-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px 10px; font-size: 11px; font-weight: 700; color: var(--ink-400); text-transform: uppercase; letter-spacing: 0.08em; }
    .folder-tree-header span { display: flex; align-items: center; gap: 6px; }
    .folder-tree-header button { border: none; background: none; cursor: pointer; font-size: 11px; color: var(--accent); font-weight: 600; padding: 3px 8px; border-radius: var(--radius-sm); transition: background 0.15s, color 0.15s; }
    .folder-tree-header button:hover { background: var(--accent-light); color: var(--accent-hover); }"""

new_folder = """.folder-tree { border-bottom: 1px solid var(--border); }
    .folder-tree-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px 8px; font-size: 11px; font-weight: 700; color: var(--ink-400); text-transform: uppercase; letter-spacing: 0.06em; }
    .folder-tree-header span { display: flex; align-items: center; gap: 5px; }
    .folder-tree-header button { border: none; background: none; cursor: pointer; font-size: 11px; color: var(--accent); font-weight: 600; padding: 2px 6px; border-radius: var(--radius-xs); transition: background 0.12s; }
    .folder-tree-header button:hover { background: var(--accent-light); }"""
html = html.replace(old_folder, new_folder)

# ── 18. Folder items: clean ─────────────────────────────────
old_fitem = """.folder-item {
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

new_fitem = """.folder-item {
      display: flex;
      align-items: center;
      padding: 6px 16px;
      cursor: pointer;
      font-size: 13px;
      color: var(--ink-600);
      border-radius: 0;
      transition: background 0.12s, color 0.12s;
      gap: 6px;
      position: relative;
      font-weight: 400;
    }
    .folder-item:hover { background: var(--paper-3); color: var(--ink-800); }
    .folder-item.active {
      background: var(--accent-light);
      color: var(--accent);
      font-weight: 600;
    }
    .folder-item.active::before {
      content: '';
      position: absolute;
      left: 0; top: 3px; bottom: 3px;
      width: 2px;
      background: var(--accent);
      border-radius: 0 2px 2px 0;
    }"""
html = html.replace(old_fitem, new_fitem)

# ── 19. Paper list header: clean ─────────────────────────────
old_plist_h = """.paper-list { flex: 1; overflow-y: auto; padding: 12px 16px 20px; }
    .paper-list h3 { font-size: 12px; font-weight: 700; color: var(--ink-400); margin-bottom: 10px; display: flex; align-items: center; gap: 6px; text-transform: uppercase; letter-spacing: 0.06em; }"""

new_plist_h = """.paper-list { flex: 1; overflow-y: auto; padding: 10px 14px 16px; }
    .paper-list h3 { font-size: 11px; font-weight: 700; color: var(--ink-400); margin-bottom: 8px; display: flex; align-items: center; gap: 5px; text-transform: uppercase; letter-spacing: 0.06em; }"""
html = html.replace(old_plist_h, new_plist_h)

# ── 20. Modal: clean ─────────────────────────────────────────
old_modal = """.modal-card {
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
    }"""

new_modal = """.modal-card {
      background: var(--paper);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 24px;
      width: 380px;
      max-width: 90vw;
      box-shadow: var(--shadow-xl);
    }
    .modal-card h3 {
      font-size: 15px;
      font-weight: 700;
      color: var(--ink-900);
      margin-bottom: 14px;
    }"""
html = html.replace(old_modal, new_modal)

# ── 21. Modal backdrop ────────────────────────────────────────
old_backdrop = """#batch-move-modal-overlay, #new-folder-modal-overlay {
      position: fixed; inset: 0;
      background: rgba(15,23,42,0.6);
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      display: flex; align-items: center; justify-content: center;
      z-index: 1000;
    }"""
new_backdrop = """#batch-move-modal-overlay, #new-folder-modal-overlay {
      position: fixed; inset: 0;
      background: rgba(0,0,0,0.45);
      display: flex; align-items: center; justify-content: center;
      z-index: 1000;
    }"""
html = html.replace(old_backdrop, new_backdrop)

# ── 22. Toast: clean ──────────────────────────────────────────
old_toast = """.toast { padding: 11px 16px; border-radius: var(--radius-md); font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 10px; max-width: 360px; box-shadow: var(--shadow-lg); animation: toastIn 0.3s cubic-bezier(0.34,1.56,0.64,1) both; pointer-events: auto; border: 1px solid transparent; }
    .toast.success { background: #064e3b; color: #6ee7b7; border-color: rgba(110,231,183,0.2); }
    .toast.error   { background: #7f1d1d; color: #fca5a5; border-color: rgba(252,165,165,0.2); }
    .toast.info    { background: #1e3a5f; color: #93c5fd; border-color: rgba(147,197,253,0.2); }
    .toast.warning  { background: #78350f; color: #fcd34d; border-color: rgba(252,211,77,0.2); }"""

new_toast = """.toast { padding: 9px 14px; border-radius: var(--radius-sm); font-size: 13px; font-weight: 500; display: flex; align-items: center; gap: 8px; max-width: 320px; box-shadow: var(--shadow-lg); pointer-events: auto; }
    .toast.success { background: #064e3b; color: #6ee7b7; }
    .toast.error   { background: #7f1d1d; color: #fca5a5; }
    .toast.info    { background: #1e3a5f; color: #93c5fd; }
    .toast.warning  { background: #78350f; color: #fcd34d; }"""
html = html.replace(old_toast, new_toast)

# ── 23. Progress bar: clean ───────────────────────────────────
old_prog = """.progress-bar-wrap {
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
new_prog = """.progress-bar-wrap { height: 3px; background: var(--border); border-radius: 2px; overflow: hidden; }
    .progress-bar-fill { height: 100%; background: var(--accent); border-radius: 2px; transition: width 0.3s ease; width: 0; }"""
html = html.replace(old_prog, new_prog)

# ── 24. Citation list: clean ────────────────────────────────
old_cite = """.citation-list { margin-top: 12px; border-top: 1px solid var(--border); padding-top: 12px; }
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
    }"""

new_cite = """.citation-list { margin-top: 10px; border-top: 1px solid var(--border); padding-top: 10px; }
    .citation-list p { font-size: 11px; color: var(--ink-400); font-weight: 700; margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.05em; }
    .citation-item {
      display: flex; align-items: flex-start; gap: 8px;
      padding: 4px 0;
      border-bottom: 1px solid var(--border);
      font-size: 12px;
      color: var(--ink-600);
      line-height: 1.5;
    }
    .citation-item:last-child { border-bottom: none; }
    .citation-num {
      color: var(--accent);
      font-weight: 700;
      flex-shrink: 0;
      min-width: 20px;
    }"""
html = html.replace(old_cite, new_cite)

# ── 25. Auth screen background: simple gray ──────────────────
old_auth_screen = """    #auth-screen {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--gradient-hero);
      padding: 20px;
    }"""
new_auth_screen = """    #auth-screen {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--paper-2);
      padding: 20px;
    }"""
html = html.replace(old_auth_screen, new_auth_screen)

# ── 26. Thinking block: clean ────────────────────────────────
old_think = """.thinking-block {
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

new_think = """.thinking-block {
      background: var(--paper-3);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 8px 12px;
      margin-bottom: 6px;
      font-size: 12px;
      color: var(--ink-500);
      cursor: pointer;
    }
    .thinking-block:hover { border-color: var(--border-2); }
    .thinking-block summary {
      font-weight: 600;
      color: var(--ink-600);
      cursor: pointer;
      user-select: none;
      list-style: none;
    }
    .thinking-block summary::marker { display: none; }
    .thinking-content {
      margin-top: 8px;
      color: var(--ink-600);
      line-height: 1.6;
      border-top: 1px solid var(--border);
      padding-top: 8px;
    }"""
html = html.replace(old_think, new_think)

# ── 27. Chat messages: clean ────────────────────────────────
old_cmessages = """.chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 20px 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      scroll-behavior: smooth;
    }"""
new_cmessages = """.chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }"""
html = html.replace(old_cmessages, new_cmessages)

# ── 28. Chat error: clean ────────────────────────────────────
old_cerr = """.chat-error {
      font-size: 13px;
      color: var(--danger);
      padding: 10px 16px;
      background: var(--danger-bg);
      border: 1px solid rgba(220,38,38,0.15);
      border-radius: var(--radius-md);
      margin: 8px 20px;
      font-weight: 500;
    }"""
new_cerr = """.chat-error {
      font-size: 12px;
      color: var(--danger);
      padding: 8px 12px;
      background: var(--danger-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      margin: 6px 16px;
    }"""
html = html.replace(old_cerr, new_cerr)

# ── 29. Error msg: clean ─────────────────────────────────────
old_err = """.error-msg { font-size: 12px; color: var(--danger); margin-top: 6px; min-height: 18px; font-weight: 500; }"""
new_err = """.error-msg { font-size: 12px; color: var(--danger); margin-top: 4px; min-height: 16px; }"""
html = html.replace(old_err, new_err)

# ── 30. Quality warning: clean ───────────────────────────────
old_qwarn = """.quality-warning {
      font-size: 12px;
      color: var(--warning);
      background: var(--warning-bg);
      border: 1px solid rgba(217,119,6,0.2);
      border-radius: var(--radius-md);
      padding: 10px 14px;
      margin: 10px 0;
      font-weight: 500;
    }"""
new_qwarn = """.quality-warning {
      font-size: 12px;
      color: var(--warning);
      background: var(--warning-bg);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 7px 10px;
      margin: 6px 0;
    }"""
html = html.replace(old_qwarn, new_qwarn)

# ── 31. Remove blur from all remaining elements ──────────────
html = html.replace('backdrop-filter: blur(8px);', '')
html = html.replace('-webkit-backdrop-filter: blur(8px);', '')

# ── 32. Fix shadow-hover to remove indigo color ──────────────
html = html.replace('box-shadow: var(--shadow-hover);', 'box-shadow: var(--shadow-hover);')
# Ensure shadow-hover doesn't have indigo
html = html.replace('rgba(79,70,229,0.13), 0 1px 4px rgba(0,0,0,0.06)', '0 2px 8px rgba(0,0,0,0.08)')
html = html.replace('rgba(129,140,248,0.15), 0 1px 4px rgba(0,0,0,0.3)', '0 2px 8px rgba(0,0,0,0.35)')

# ── 33. Verify brackets ──────────────────────────────────────
import re
styles = re.findall(r'<style>(.*?)</style>', html, re.DOTALL)
css = styles[0]
opens = css.count('{')
closes = css.count('}')
print(f"CSS brackets: {{ ={opens}, }} ={closes}, diff={opens-closes}")

scripts = re.findall(r'<script(.*?)</script>', html, re.DOTALL)
for i, s in enumerate(scripts):
    o = s.count('{')
    c = s.count('}')
    if o != c:
        print(f"Script block {i}: {{ ={o}, }} ={c} ❌")
    else:
        print(f"Script block {i}: ✅ balanced")

print(f"New size: {len(html)}")

# ── 34. Save ─────────────────────────────────────────────────
with open('/var/www/rag/index.html', 'w') as f:
    f.write(html)
print("✅ Elicit CSS redesign complete!")
