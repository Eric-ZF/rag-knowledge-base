# React 重构计划 — Phase 0 Frontend

> 将 2100 行 Vanilla JS 单文件重构为 React 18 + Vite 组件化架构

---

## 一、现状分析

### 当前问题

| 问题 | 影响 |
|------|------|
| 2100 行单文件，无组件化 | 新功能开发效率低，改一处毁三处 |
| CSS 全部写在一起（26826 字节）| 样式冲突难以追踪，Elicit 风格改了半天仍有问题 |
| 全局 `let` 状态（token/userId/folders/papers）| 状态不可预测，调试困难 |
| 所有函数都挂在 `window` | 命名冲突风险 |
| SSE/chat 流式处理耦合在 UI 逻辑里 | 重用几乎不可能 |

### 现有全局状态（需要 React Context）

```javascript
let token           // JWT token
let userPhone       // 登录手机号
let userId          // 用户 ID
let plan            // 套餐
let chatMode        // 'default' | 'methodology' | 'survey'
let folders         // 文件夹列表
let currentFolderId // 当前选中文件夹
let papers          // 当前文件夹论文列表
let messages        // 聊天消息历史
let pendingUploads  // 上传队列
let uploading = false
let sending = false
let selectedPapers  // 批量选中论文
let batchMode       // 批量选择模式
```

---

## 二、技术栈

| 层 | 选型 | 理由 |
|---|------|------|
| 框架 | **React 18** | 稳定，生态成熟 |
| 构建 | **Vite 4** | 快，配置简单，HMR 开发体验好 |
| 样式 | **Tailwind CSS v3** (CDN) | CSS-in-JS 不用引入，支持 JIT |
| 状态 | **React Context + useReducer** | 无需 Redux，小项目足够 |
| Markdown | **marked.js** (CDN, 现有) | 继续用已有的 |
| 图标 | **Lucide React** | 轻量，tree-shakable |
| HTTP | **fetch** (内置) | 无需 axios |
| 部署 | nginx 静态托管（不变）| 构建产物复制到 `/var/www/rag/` |

---

## 三、目录结构

```
frontend/
├── index.html           # 入口（极简，只 mount #root）
├── vite.config.js      # Vite 配置
├── package.json
├── public/             # 静态资源（favicon 等）
└── src/
    ├── main.jsx         # React 入口
    ├── App.jsx          # 根组件 + 全局状态
    ├── index.css        # Tailwind 入口 + CSS 变量
    │
    ├── contexts/
    │   ├── AuthContext.jsx      # token / userId / login / logout
    │   └── ChatContext.jsx       # messages / sendMessage / streaming
    │
    ├── components/
    │   ├── AuthScreen.jsx       # 登录/注册
    │   ├── AppLayout.jsx         # 主布局（header + main grid）
    │   │
    │   ├── left/
    │   │   ├── FolderTree.jsx          # 文件夹树
    │   │   ├── FolderItem.jsx          # 单个文件夹项
    │   │   ├── NewFolderModal.jsx     # 新建文件夹弹框
    │   │   ├── UploadZone.jsx          # 拖拽上传区
    │   │   ├── UploadProgress.jsx     # 上传进度条
    │   │   └── PaperList.jsx           # 论文列表容器
    │   │       ├── PaperCard.jsx        # 单个论文卡片
    │   │       └── BatchMoveModal.jsx   # 批量移动弹框
    │   │
    │   ├── right/
    │   │   ├── QuotaBanner.jsx   # 顶部用量提示
    │   │   ├── ChatPanel.jsx     # 聊天主面板
    │   │   │   ├── ChatMessage.jsx     # 单条消息气泡
    │   │   │   ├── ThinkingBlock.jsx   # 思考过程折叠块
    │   │   │   ├── CitationList.jsx    # 引用列表
    │   │   │   └── QualityWarning.jsx  # 质量警告
    │   │   └── ChatInput.jsx     # 输入框 + 模式切换
    │   │
    │   └── shared/
    │       ├── Toast.jsx         # Toast 通知
    │       ├── Modal.jsx         # 通用弹框
    │       └── LoadingSpinner.jsx
    │
    └── lib/
        ├── api.js         # HTTP 请求封装（token 自动注入）
        ├── storage.js     # localStorage 读写
        ├── markdown.js   # marked.js 配置 + AST 过滤
        └── constants.js  # API_BASE, CHAT_MODES 等
```

---

## 四、组件设计

### 4.1 状态流

```
App (useReducer)
  ├── AuthContext.Provider
  │   └── { token, userId, userPhone, login(), logout() }
  └── ChatContext.Provider
      └── { messages, sending, chatMode, sendMessage() }
```

### 4.2 组件树

```
<App>
  { token ? (
    <AppLayout>
      <FolderTree>
        <FolderItem />
        <NewFolderModal />
      <UploadZone>
        <UploadProgress />
      <PaperList>
        <PaperCard /> × N
        <BatchMoveModal />
      <ChatPanel>
        <ChatMessage /> × M
        <ThinkingBlock />
        <CitationList />
        <QualityWarning />
      <ChatInput>
    </AppLayout>
  ) : (
    <AuthScreen />
  ) }
  <Toast /> (全局)
  <Modal /> (按需)
</App>
```

### 4.3 关键 Hooks

```javascript
// useAuth - 认证状态
const { token, userId, login, logout } = useAuth()

// useChat - 聊天状态
const { messages, sending, chatMode, setChatMode, sendMessage } = useChat()

// useFolders - 文件夹 CRUD
const { folders, currentFolderId, selectFolder, createFolder } = useFolders()

// usePapers - 论文列表（按文件夹过滤）
const { papers, loading, uploadPapers, deletePaper, movePapers } = usePapers()

// useSSE - SSE 流式（ChatPanel 内部使用）
const { startStream, abortStream } = useSSE(onChunk, onDone, onError)
```

---

## 五、实施计划

### Week 1：基础架构（第 1-3 天）

| 任务 | 说明 |
|------|------|
| 初始化 Vite + React 项目 | `npm create vite@latest frontend -- --template react` |
| 配置 Tailwind CSS (CDN) | PostCSS 不走构建，CDN 直接用 |
| 迁移 `api.js` | 把 fetch 封装从原 JS 搬过来 |
| 实现 AuthContext | login/logout/setPassword + localStorage |
| 实现 AuthScreen | 登录注册 UI（样式尽量复刻现有）|
| nginx 配置更新 | 静态文件路径指向 `frontend/dist/` |
| 验证登录流程 | 和现有行为 100% 一致 |

**交付物**：可以登录/登出，其他功能暂时不可用

### Week 1：核心功能（第 4-5 天）

| 任务 | 说明 |
|------|------|
| 实现 AppLayout | 左右分栏 grid 布局 |
| 实现 FolderTree + CRUD | 创建/选择/删除文件夹 |
| 实现 UploadZone + SSE | 拖拽上传 + 实时进度 |
| 实现 PaperList + PaperCard | 论文卡片列表 |
| 实现 BatchMoveModal | 批量移动功能 |
| 验证完整上传流程 | 端到端测试 |

**交付物**：左侧面板完整可用，和现有功能一致

### Week 2：聊天功能（第 1-2 天）

| 任务 | 说明 |
|------|------|
| 实现 ChatContext | messages 状态 + sendMessage |
| 实现 ChatPanel + ChatMessage | 消息气泡渲染 |
| 实现 SSE 流式接收 | `useSSE` hook |
| 实现 ThinkingBlock | 思考折叠 |
| 实现 CitationList | 引用列表渲染 |
| 实现 marked.js AST 过滤 | 复用现有的 stripReferenceTokens |

**交付物**：聊天功能完整可用

### Week 2：打磨（第 3-5 天）

| 任务 | 说明 |
|------|------|
| 实现 QualityWarning | 差评质量分数展示 |
| 实现 ChatMode 切换 | default / methodology / survey |
| 样式 Elicit 化 | 按 Elicit 风格重写 CSS（这次 CSS 隔离不会互相污染）|
| 深色模式 | Tailwind `dark:` class |
| 响应式适配 | 移动端抽屉式侧边栏 |
| 部署验证 | nginx + systemd 重启流程 |
| Bug 修复 + 回归测试 | 全流程端到端验证 |

**交付物**：生产可用

---

## 六、样式方案（Elicit 克制风格）

### Tailwind 配置（tailwind.config.js）

```javascript
module.exports = {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ink: {
          900: '#111827', 800: '#1f2937', 700: '#374151',
          600: '#4b5563', 500: '#6b7280', 400: '#9ca3af',
        },
        paper: { DEFAULT: '#ffffff', 2: '#f9fafb', 3: '#f3f4f6' },
        accent: { DEFAULT: '#2563eb', hover: '#1d4ed8' },
      },
      boxShadow: {
        sm: '0 1px 2px rgba(0,0,0,0.05)',
        DEFAULT: '0 1px 3px rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)',
        hover: '0 2px 8px rgba(0,0,0,0.08)',
        lg: '0 4px 16px rgba(0,0,0,0.1)',
        xl: '0 8px 32px rgba(0,0,0,0.12)',
      },
      borderRadius: { sm: '5px', DEFAULT: '8px', lg: '10px' },
    },
  },
}
```

### CSS 变量（index.css）

```css
:root {
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --accent-light: rgba(37,99,235,0.06);
  --border: #e5e7eb;
  --border-2: #d1d5db;
}
```

### 核心 Tailwind 类使用

```jsx
// 论文卡片
<div className="bg-white border border-[#e5e7eb] rounded-lg p-3 mb-2
            hover:shadow-hover hover:border-accent/20 transition-all">

// 聊天气泡
<div className="bg-white border border-[#e5e7eb] rounded-lg px-4 py-2.5 text-sm text-[#374151]">

// 发送按钮
<button className="bg-accent text-white rounded px-4 py-2 font-semibold
                  hover:bg-accent-hover transition-colors">

// 文件夹选中
<div className="bg-accent-light text-accent font-semibold border-l-2 border-accent">
```

---

## 七、API 层（src/lib/api.js）

```javascript
const API_BASE = 'http://124.156.204.163:8080'

async function api(method, path, body, noAuth = false) {
  const headers = { 'Content-Type': 'application/json' }
  if (!noAuth && token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const opts = { method, headers }
  if (body) opts.body = JSON.stringify(body)
  const r = await fetch(`${API_BASE}${path}`, opts)
  const data = await r.json()
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`)
  return data
}

export const login = (phone, password) =>
  api('POST', '/auth/login', { phone, password }, true)

export const getPapers = () =>
  api('GET', '/papers')

export const getFolders = () =>
  api('GET', '/folders')

export const createFolder = (name, parentId) =>
  api('POST', '/folders', { name, parent_id: parentId })

export const uploadPaper = (formData) => { ... }  // multipart

export const sendChat = (body) =>
  api('POST', '/chat', body, false, 120000)

export const movePapers = (paperIds, folderId) =>
  api('POST', '/papers/move', { paper_ids: paperIds, folder_id: folderId })
```

---

## 八、部署流程

### 开发

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

### 构建

```bash
npm run build       # 产物 → frontend/dist/
cp -r dist/* /var/www/rag/
sudo systemctl restart rag-backend
```

### nginx 配置（不变）

现有 nginx 已经托管 `/var/www/rag/` 静态目录，构建产物复制过去即可。

---

## 九、风险与缓解

| 风险 | 缓解 |
|------|------|
| 重构期间功能损坏 | **平行部署**：React app 放 `/app/`，nginx 配置切换开关，坏了可秒切回原版 |
| SSE 流式处理复杂 | `useSSE` hook 单独测试，OK 后再接入 ChatPanel |
| API URL 硬编码 | 构建时注入 `VITE_API_BASE`，测试/生产分离 |
| 样式不一致 | 参考现有 `index.html` 的 CSS 值，逐组件迁移验证 |
| 部署后出现未知 bug | 回滚：把 `index.html` 重新复制到 `/var/www/rag/`，重启 nginx |

---

## 十、零风险部署策略

### 平行部署（推荐）

```
当前状态:  /var/www/rag/index.html  → Vanilla JS

重构完成:  /var/www/rag/index.html  → nginx 指向 original/ (备份)
          /var/www/rag/app/         → React 构建产物

切换方式:  修改 nginx root 一行配置，nginx reload
回滚方式:  改回 root，nginx reload（5 秒回滚）
```

**备份原版：**
```bash
cp -r /var/www/rag /var/www/rag.original_backup
```

**切换脚本：**
```bash
# 切换到 React
cp -r /root/.openclaw/workspace/rag-knowledge-base/phase0/frontend/dist/* /var/www/rag/
# 回滚到原版
cp -r /var/www/rag.original_backup/* /var/www/rag/
```

---

## 十一、Tailwind CDN 方案（无构建）

不需要 npm + PostCSS + Vite CSS 处理，直接用 CDN script，最快上手：

```html
<!-- index.html (React app) -->
<!DOCTYPE html>
<html>
<head>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            ink: { 900:'#111827', 800:'#1f2937', 700:'#374151', ... },
            accent: { DEFAULT: '#2563eb', hover: '#1d4ed8' }
          }
        }
      }
    }
  </script>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
```

**优点：**
- 无需 `npm install tailwindcss`
- 无需 PostCSS 配置
- CSS 类在浏览器实时 JIT 编译
- 开发时 `vite dev` 正常，生产构建 CSS bundle 极小

---

## 十二、压缩版里程碑（5-7 天）

| 里程碑 | 目标 | 验收标准 |
|--------|------|----------|
| **M0: 脚手架** | Day 1 上午 | Vite + React 跑通，AuthScreen 能登录 |
| M1: 左侧完整 | Day 2-3 | 文件夹+上传+论文列表 100% 功能 |
| M2: 聊天完整 | Day 4-5 | 提问+流式+引用展示正常 |
| M3: 生产上线 | Day 6-7 | 全流程端到端，nginx 切换完成 |

**每天一个小里程碑，降低延期风险。**
