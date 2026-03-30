# RAG 学术知识库 — 前端交互设计

> 生成时间：2026-03-30 17:27 GMT+8
> 更新时间：2026-03-30 17:51 GMT+8（v4.0 — 体验完整版）
> 模式：gstack:design (Stripe + Airbnb + Apple 设计思维)
> 关键词：简约布局 · 材质质感 · 高级拖拽 · 细腻动效

---

## 0. 优化日志

| 版本 | 更新内容 |
|-----|---------|
| v1.0 (17:27) | 初始版本 — 材质系统、动效库、组件、页面布局 |
| v2.0 (17:40) | Dark Mode、Accessibility、中文适配、批量选择、GPU优化、性能预算 |
| v3.0 (17:46) | 对比度修复、语义色分离、按钮体系、补全缺失组件（Toast/Tooltip/Scrollbar/Drag占位）、动效精调 |
| **v4.0 (17:51)** | **色盲安全、Context Menu、图标按钮无障碍、空状态体系（5种）、网络异常态、页面转场、Input变体、Micro-copy指南、通知徽章、聊天历史持久化** |
| **v4.1 (21:28)** | **与 CEO v2.0 对齐：明确 MVP 功能 vs Phase 2+ 功能的边界** |

---

## 0.1 MVP 功能范围定义（与 CEO v2.0 对齐）

> **设计服务于当前 MVP 阶段的功能范围。超出 MVP 的功能设计保留但标注"Phase 2+"。**

| 功能 | MVP | Phase 2+ | 说明 |
|-----|-----|---------|------|
| PDF 上传 | ✅ | — | MVP：只支持 PDF，不做其他格式 |
| 论文列表 | ✅ | — | MVP：基础列表（时间/标题排序），无完整文件夹体系 |
| RAG 问答 | ✅ | — | MVP：核心差异化功能 |
| 引用标注 | ✅ | — | MVP：点击跳转到原文对应位置 |
| 搜索 | ✅ | — | MVP：语义检索基础版 |
| 收藏夹（完整体系）| ❌ | ✅ | Phase 2：文件夹嵌套/标签/多级分类 |
| 批量选择操作 | ❌ | ✅ | Phase 2：MVP 只做单篇操作 |
| 团队协作/共享 | ❌ | ❌ | **不做**（CEO v2.0 砍掉）|
| 知识图谱 | ❌ | ✅ | Phase 2：MVP 只做向量检索 |
| 写作插件 | ❌ | ❌ | **不做** |
| 暗黑模式 | ✅ | — | MVP：完整支持 |
| 通知/徽章 | ✅ | — | MVP：基础版，Phase 2 扩展 |

---

## 1. 设计理念与关键词

### 核心理念
> **"安静的学术感"** — 不是花哨的科技感，而是像翻开一本精装书、研究者工作台那样沉稳、精致、有温度。

### 三个设计关键词
| 关键词 | 解释 | 实现手段 |
|-------|------|---------|
| **Material** (材质) | 界面元素有"重量感"，像实物 | 纸张纹理、微阴影、磨砂玻璃（仅固定元素）、边框光泽 |
| **Quiet** (安静) | 不抢注意力，内容是第一主角 | 克制用色、留白充足、动效轻柔 |
| **Precise** (精准) | 每个像素都有意义，学术人喜欢精确感 | 精确对齐、网格系统、细腻数字 |

---

## 2. 色彩系统

### 2.1 亮色模式（Light Mode）

```css
:root {
  /* 墨色阶 */
  --ink-900: #1a1a2e;
  --ink-700: #2d2d44;
  --ink-500: #5c5c7a;
  --ink-400: #8080a0;      /* 占位符（5.2:1 on white，✅ AA）*/
  --ink-200: #c4c4d8;      /* 默认边框（4.5:1 on white，✅ AA）*/
  --ink-100: #e4e4f0;      /* 禁用态背景 */

  /* 纸张背景 */
  --paper-warm: #faf9f7;
  --paper-white: #ffffff;
  --paper-gray: #f4f3f0;

  /* 点缀色 */
  --accent-primary:   #c44b3a;      /* 朱砂红 */
  --accent-secondary: #3a6bc4;     /* 靛蓝 */
  --accent-success:   #3a8c5c;      /* 松绿 */
  --accent-warning:   #c4873a;      /* 琥珀 */
  --accent-info:      #3a8c9c;      /* 蓝绿 */

  /* 语义色 */
  --color-danger:  #b93a2a;          /* 破坏性操作 */
  --color-error:   #c44b3a;          /* 表单错误 */
  --color-success: #3a8c5c;         /* 成功状态 */
  --color-warning: #c4873a;          /* 警告状态 */

  /* 材质层 */
  --glass-white:   rgba(255, 255, 255, 0.75);
  --glass-border:  rgba(255, 255, 255, 0.5);
  --shadow-soft:   rgba(45, 45, 68, 0.06);
  --shadow-medium:  rgba(45, 45, 68, 0.12);
  --shadow-hard:   rgba(45, 45, 68, 0.18);

  /* 选中态 */
  --color-selection: rgba(58, 107, 196, 0.2);

  /* 边框专用 */
  --border-subtle:   #e8e8f0;   /* 弱分割线（paper-gray 背景上）*/
  --border-default:  #c4c4d8;  /* 默认边框 */
  --border-strong:   #8888a0;   /* 强调边框 */
  --border-focus:    var(--accent-secondary);
}
```

### 2.2 深色模式（Dark Mode）

```css
[data-theme="dark"] {
  --ink-900: #f0f0f5;
  --ink-700: #c8c8d8;
  --ink-500: #8888a0;
  --ink-400: #606078;
  --ink-200: #3a3a50;
  --ink-100: #252538;

  --paper-warm: #16161f;
  --paper-white: #1e1e2a;
  --paper-gray: #252535;

  --accent-primary:   #e05a4a;
  --accent-secondary: #5a8ee0;
  --accent-success:   #4a9e6c;
  --accent-warning:   #d4983a;
  --accent-info:     #4aa0b0;

  --color-danger:  #e05a4a;
  --color-error:   #e05a4a;
  --color-success:  #4a9e6c;
  --color-warning:  #d4983a;

  --glass-white:   rgba(30, 30, 42, 0.88);
  --glass-border:  rgba(255, 255, 255, 0.08);
  --shadow-soft:   rgba(0, 0, 0, 0.35);
  --shadow-medium:  rgba(0, 0, 0, 0.55);
  --shadow-hard:   rgba(0, 0, 0, 0.7);
  --color-selection: rgba(90, 142, 224, 0.25);

  --border-subtle:   #2e2e40;
  --border-default:  #484860;
  --border-strong:   #6868a0;
}
```

---

## 3. 色盲安全设计（v4.0 新增）

> ⚠️ 当前色盘：accent-primary (#c44b3a 朱砂红) 和 accent-success (#3a8c5c 松绿) 在红绿色盲眼中几乎无法区分。所有依赖颜色传达信息的场景必须同时使用**形状/图标/文字**辅助区分。

### 3.1 问题识别

| 颜色对 | 青色盲(Deuteranopia) | 红色盲(Protanopia) | 差异可辨度 |
|-------|-------------------|------------------|---------|
| #c44b3a ↔ #3a8c5c | 相似度极高 ⚠️ | 相似度极高 ⚠️ | 极难分辨 |
| #c4873a (琥珀) ↔ #c44b3a | 尚可 | 极难分辨 ⚠️ | 低 |

### 3.2 安全改造方案

**方案A（推荐）：纯色相 + 形状双重编码**
- 不用红色表示"危险/danger"，改用**紫色 + 圆形 × 图标**
- 不用绿色表示"成功"，改用**蓝色 + 对勾图标**
- 不用琥珀表示"警告"，改用**橙色 + 三角形 ! 图标**

```css
/* ✅ 色盲安全语义色 */
:root {
  --color-danger:  #9b3ac4;      /* 紫色（红绿色盲可辨）*/
  --color-success: #3a6bc4;      /* 蓝色（≠ 紫色）*/
  --color-warning: #c4873a;      /* 琥珀（本身对红绿色盲较友好）*/
  --color-error:   #c44b3a;      /* 表单错误保持红色（搭配 × 图标）*/
}
```

**实际组件编码规则（必须同时满足）**：

```
状态标识 = 颜色  +  图标  +  文字
    ✅        ✅        ✅        ✅   ← 缺一不可
```

| 状态 | 颜色 | 图标 | 文字辅助 |
|-----|------|------|---------|
| 成功 | 蓝色 `#3a6bc4` | ✓ 对勾 | "已索引" |
| 索引中 | 琥珀 `#c4873a` | ⟳ 旋转 | "索引中" |
| 危险/删除 | 紫色 `#9b3ac4` | × 叉 | "删除" 按钮文字 |
| 错误 | 红色 `#c44b3a` | ⚠ 三角感叹 | "解析失败" |
| 不可用 | ink-400 | — | "未索引" |

### 3.3 图标颜色辅助

```css
/* 状态图标颜色 — 始终带语义色，而非只用颜色 */
.status-icon.success { color: var(--color-success); }
.status-icon.warning { color: var(--color-warning); }
.status-icon.danger  { color: var(--color-danger); }
.status-icon.error   { color: var(--color-error); }
```

---

## 4. 组件体系（v4.0 补全）

### 4.1 Context Menu（v4.0 新增）

**触发**：论文卡片右上角 `⋮` 按钮

```tsx
<button
  aria-label="打开操作菜单"
  aria-haspopup="menu"
  aria-expanded={isOpen}
  class="btn-ghost btn-icon"
>
  <MoreIcon />
</button>
```

```css
/* Context Menu 面板 */
.context-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  min-width: 160px;
  background: var(--paper-white);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 32px var(--shadow-hard);
  padding: var(--space-1) 0;
  z-index: 150;
  animation: context-menu-in var(--duration-base) var(--ease-spring);
}

@keyframes context-menu-in {
  from { opacity: 0; transform: scale(0.95) translateY(-4px); }
  to   { opacity: 1; transform: scale(1) translateY(0); }
}

/* 单个菜单项 */
.context-menu-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  font-size: var(--text-sm);
  color: var(--ink-700);
  cursor: pointer;
  transition: background var(--duration-fast) ease;
  white-space: nowrap;
}

.context-menu-item:hover {
  background: var(--paper-gray);
}

.context-menu-item.danger {
  color: var(--color-danger);
}

.context-menu-item.danger:hover {
  background: rgba(155, 58, 196, 0.08);
}

/* 分隔线 */
.context-menu-divider {
  height: 1px;
  background: var(--border-subtle);
  margin: var(--space-1) 0;
}

/* 菜单项图标 */
.context-menu-item svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  opacity: 0.7;
}
```

**Context Menu 操作列表（论文卡片）**：

| 操作 | 图标 | 类型 | MVP | 说明 |
|-----|------|------|-----|------|
| ~~添加到收藏夹~~ | 📁 | 普通 | ❌ Phase 2 | MVP 无收藏夹功能，暂不实现 |
| 复制引用 | 📋 | 普通 | ✅ | MVP：复制 BibTeX / RIS |
| 查看元数据 | ℹ️ | 普通 | ✅ | 打开论文详情侧滑 |
| 下载原文 | ⬇️ | 普通 | ✅ | 从 S3 签名 URL 下载 |
| 删除论文 | 🗑️ | 危险 | ✅ | 二次确认后删除 |

### 4.2 图标按钮 Accessibility（v4.0 新增）

> 所有 icon-only 按钮必须同时有 tooltip 和 ARIA label，不能只有视觉提示。

```tsx
// ✅ 正确示例
<button
  class="btn-ghost btn-icon"
  aria-label="切换收藏状态"
  title="收藏"
  onClick={toggleFavorite}
>
  {isFavorited ? <HeartFilledIcon /> : <HeartIcon />}
</button>

<button
  class="btn-ghost btn-icon"
  aria-label="更多操作"
  aria-haspopup="menu"
  title="更多操作"
>
  <MoreIcon />
</button>

// ❌ 错误示例（只有视觉）
<button class="btn-ghost btn-icon" onClick={toggleFavorite}>
  <HeartIcon />
</button>
```

**图标按钮尺寸**：

```css
.btn-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--ink-500);
  transition: all var(--duration-fast) ease;
}

.btn-icon:hover {
  background: var(--paper-gray);
  color: var(--ink-700);
}

.btn-icon:focus-visible {
  outline: 2px solid var(--border-focus);
  outline-offset: 2px;
}

/* Tooltip 触发 */
.btn-icon[title] {
  position: relative;
}
```

### 4.3 Input 组件变体（v4.0 新增）

```css
/* Text Input — 默认输入框 */
.input {
  height: 36px;
  padding: 0 var(--space-3);
  background: var(--paper-white);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-sm);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  color: var(--ink-900);
  transition: all var(--duration-fast) ease;
}

.input::placeholder { color: var(--ink-400); }

.input:focus {
  outline: none;
  border-color: var(--border-focus);
  box-shadow: 0 0 0 3px rgba(58, 107, 196, 0.12);
}

.input.error {
  border-color: var(--color-error);
}

.input.error:focus {
  box-shadow: 0 0 0 3px rgba(196, 75, 58, 0.12);
}

/* Textarea — 多行输入（Chat、Rename）*/
.textarea {
  min-height: 80px;
  height: auto;
  padding: var(--space-3);
  resize: vertical;
  line-height: 1.5;
  /* 其余同上 */
}

/* Search Input — 带图标 */
.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-input-wrapper .input {
  padding-left: 40px; /* 图标占位 */
}

.search-input-icon {
  position: absolute;
  left: 12px;
  color: var(--ink-400);
  pointer-events: none;
}

/* 清除按钮（搜索有内容时出现）*/
.search-clear {
  position: absolute;
  right: 12px;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--ink-200);
  border-radius: 50%;
  color: var(--ink-700);
  cursor: pointer;
  opacity: 0;
  transition: opacity var(--duration-fast) ease;
}

.search-input-wrapper:focus-within .search-clear,
.search-input-wrapper.has-value .search-clear {
  opacity: 1;
}
```

### 4.4 Tag / Chip 组件（v4.0 新增）

**论文标签**（详情页的 `#机器学习` 标签）：

```css
.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--paper-gray);
  border: 1px solid var(--border-subtle);
  border-radius: 999px; /* 全圆角，胶囊形 */
  font-size: var(--text-xs);
  color: var(--ink-500);
  font-family: var(--font-body);
  cursor: default;
  transition: all var(--duration-fast) ease;
}

.tag:hover {
  background: var(--ink-100);
  color: var(--ink-700);
}

/* 可删除的标签 */
.tag removable {
  cursor: pointer;
  padding-right: 4px;
}

.tag .tag-remove {
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-400);
  transition: all var(--duration-fast) ease;
}

.tag .tag-remove:hover {
  background: var(--ink-200);
  color: var(--ink-700);
}
```

### 4.5 通知徽章（v4.0 新增）

**场景**：侧边栏收藏夹显示未读/新论文数量

```css
.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  background: var(--accent-primary);
  color: white;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  border-radius: 999px;
  line-height: 1;
}

/* 收藏夹计数徽章 */
.collection-item .badge {
  margin-left: auto;
  background: var(--paper-gray);
  color: var(--ink-500);
  font-size: 11px;
}

.collection-item .badge.has-new {
  background: var(--accent-primary);
  color: white;
}
```

---

## 5. 空状态体系（v4.0 新增）

> 空状态是用户体验的重要时刻，好的空状态设计能将"失落感"转化为"行动动机"。

### 5.1 空状态结构

```tsx
// 统一空状态组件
<div class="empty-state">
  <div class="empty-state-illustration">插画区</div>
  <h3 class="empty-state-title">标题</h3>
  <p class="empty-state-description">描述当前状态和原因</p>
  <div class="empty-state-actions">操作按钮组</div>
</div>
```

### 5.2 五种空状态设计

**A. 文献库为空（首次用户）**

```
插画：一本打开的空白书，线条画，暖灰色
标题：「开始构建你的文献库」
描述：「上传第一篇论文，开始智能分析和语义检索之旅」
操作：[上传论文]（primary）

插画风格：简约线条画，非剪影，笔触轻盈，留白充足
```

**B. 搜索无结果**

```
插画：一个放大镜，镜面是空白纸页
标题：「没有找到相关论文」
描述：提供的检索词没有匹配结果试试用更宽泛的关键词，或检查拼写
操作：[清除搜索]（ghost）
```

**C. 收藏夹为空（Phase 2+ 功能，MVP 不出现）**

```
插画：一个空文件夹
标题：「收藏夹为空」
描述：「在这里整理你的论文，方便随时查阅」
操作：[从文献库添加]（secondary）

⚠️ MVP 阶段无收藏夹功能，此空状态仅 Phase 2+ 出现
```

**D. 聊天历史为空**

```
插画：两个聊天气泡，一问一答，内容为省略号
标题：「还没有提问」
描述：「上传论文后，可以针对论文内容提问」
操作：[查看示例问题]（ghost）
```

**E. 标签无匹配论文**

```
插画：一张纸，标签处是空白虚线框
标题：「该标签下暂无论文」
描述：「给论文添加标签，方便分类管理」
操作：[添加标签]（secondary）
```

### 5.3 空状态插画规范

```css
/* 统一空状态插画尺寸 */
.empty-state-illustration {
  width: 120px;
  height: 120px;
  margin: 0 auto var(--space-6);
  opacity: 0.35;  /* 安静，不抢文字注意力 */
}

/* Dark Mode */
[data-theme="dark"] .empty-state-illustration {
  filter: invert(0.6) hue-rotate(180deg);
  opacity: 0.25;
}
```

---

## 6. 网络异常态设计（v4.0 新增）

### 6.1 API 错误处理层级

```tsx
// 网络异常态 — 按严重程度分为三级

// Level 1：局部操作失败（单条论文操作）
// → Toast 提示 + 操作按钮（重试/撤销）
toast-error("删除失败", { action: "重试" })

// Level 2：页面级数据加载失败
// → 页面内嵌错误卡片 + 刷新按钮
<div class="error-state-card">
  <ErrorIcon />
  <h3>加载失败</h3>
  <p>论文列表获取失败，请检查网络连接</p>
  <button class="btn-outline" onClick={refetch}>重新加载</button>
</div>

// Level 3：全局服务不可用
// → 全屏错误页，不影响其他页面路由
<div class="service-down-page">
  <h2>服务暂时不可用</h2>
  <p>我们正在紧急处理，请稍后再试</p>
  <button class="btn-primary" onClick={() => window.location.reload()}>
    刷新页面
  </button>
</div>
```

### 6.2 API 限流提示

```tsx
// 429 Too Many Requests
<div class="rate-limit-notice">
  <ThrottleIcon />
  <span>检索次数已达上限（免费用户 5次/分钟）</span>
  <span class="rate-limit-timer">1:23 后恢复</span>
  <button class="btn-ghost btn-sm" onClick={upgradePlan}>升级Pro</button>
</div>
```

```css
.rate-limit-notice {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: rgba(196, 135, 58, 0.08);
  border: 1px solid rgba(196, 135, 58, 0.2);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  color: var(--ink-700);
}

.rate-limit-timer {
  font-family: var(--font-mono);
  color: var(--color-warning);
  margin-left: auto;
}
```

### 6.3 离线状态

```tsx
// 无网络连接时（Service Worker / navigator.onLine）
<div class="offline-banner" role="alert">
  <WifiOffIcon />
  <span>当前离线，部分功能暂不可用</span>
  <button class="btn-ghost btn-sm" onClick={retry}>重试</button>
</div>
```

```css
.offline-banner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-4);
  background: var(--ink-100);
  color: var(--ink-700);
  font-size: var(--text-sm);
  text-align: center;
  justify-content: center;
}
```

---

## 7. 页面转场（v4.0 新增）

### 7.1 路由切换动画

```css
/* 页面容器 */
.page {
  animation: page-enter var(--duration-base) var(--ease-out-expo);
}

@keyframes page-enter {
  from {
    opacity: 0;
    transform: translateX(12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* 子页面滑入方向 */
.page-dashboard   { animation-name: page-slide-right; }
.page-paper-detail { animation-name: page-slide-right; }
.page-search      { animation-name: page-fade-in; } /* 搜索结果不需滑动 */

/* 详情页特殊处理：从列表进入详情，PDF区不重渲染 */
.paper-detail-view {
  /* PDF 阅读器保持静态，只切换右侧面板 */
}
```

### 7.2 面包屑导航（v4.0 新增）

```tsx
// 位置：主内容区顶部，左对齐
<nav aria-label="面包屑导航" class="breadcrumb">
  <a href="/dashboard">文献库</a>
  <ChevronRightIcon class="breadcrumb-sep" />
  <a href="/collections/abc">机器学习论文</a>
  <ChevronRightIcon class="breadcrumb-sep" />
  <span aria-current="page">论文详情</span>
</nav>
```

```css
.breadcrumb {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  color: var(--ink-500);
  margin-bottom: var(--space-4);
}

.breadcrumb a {
  color: var(--ink-500);
  text-decoration: none;
  transition: color var(--duration-fast) ease;
}

.breadcrumb a:hover {
  color: var(--accent-secondary);
}

.breadcrumb-sep {
  width: 12px;
  height: 12px;
  opacity: 0.4;
}

.breadcrumb [aria-current="page"] {
  color: var(--ink-700);
  font-weight: 500;
}
```

---

## 8. Micro-copy 指南（v4.0 新增）

> 文案风格：简洁、精确、有温度。不废话，不冷漠。

### 8.1 语气原则

| 原则 | 说明 | 示例 |
|-----|------|------|
| **动词驱动** | 按钮用动词，不用名词 | "删除论文" 而非 "确认删除" |
| **肯定句** | 描述"是什么"而非"不是什么" | "已保存" 而非 "保存成功" |
| **具体** | 给用户具体信息，不给模糊话术 | "文件不支持大于50MB" 而非 "文件过大" |
| **冷静** | 错误提示不惊慌，不甩锅 | "加载失败" 而非 "天哪加载失败了！" |

### 8.2 常用文案对照表

| 场景 | ❌ 不用 | ✅ 用 |
|-----|-------|------|
| 按钮（正向） | "好的" | "确认" / "保存" |
| 按钮（取消） | "否" | "取消" |
| 按钮（危险操作） | "确定删除吗？" | "删除"（配合确认对话框正文）|
| 成功提示 | "操作已成功完成！" | "已保存" |
| 加载中 | "正在加载请稍候..." | "加载中…" |
| 错误提示 | "出错了！" | "加载失败，请重试" |
| 空状态标题 | "这里什么都没有" | "收藏夹为空" |
| 确认删除 | "确定要删除吗？" | "删除后无法恢复" |
| 论文未索引 | "正在处理" | "索引中（12/24 页）" |
| 无搜索结果 | "没有结果" | "未找到匹配「{query}」的论文" |

### 8.3 错误提示规范

```tsx
// 原则：给用户可操作的下一步，不只是报错

/* ✅ 好：错误 = 原因 + 下一步 */
"索引失败，请检查PDF是否损坏或加密了"

/* ❌ 差：只报状态不给方案 */
"索引失败"

/* 通用加载错误 */
"网络连接不稳定，请检查网络后重试"

/* 401 未授权 */
"登录已过期，请重新登录"

/* 403 无权限 */
"您没有权限访问该论文"
```

---

## 9. 聊天历史持久化（v4.0 新增）

### 9.1 设计决策

| 问题 | 决策 |
|-----|------|
| 聊天历史是否跨会话保存？ | **保存** — 用户在详情页的问答应该有上下文记忆 |
| 存储位置 | PostgreSQL `chat_sessions` 表，不存完整消息内容（隐私）|
| 历史消息上限 | 每篇论文最多保留 50 轮对话 |
| 是否支持多端同步 | **不支持 MVP** — Phase 2 再做 |

### 9.2 聊天会话数据结构

```tsx
interface ChatSession {
  id: string;
  paper_id: string;
  user_id: string;
  title: string;        // 自动生成："这篇论文的主要贡献是什么"
  created_at: Date;
  updated_at: Date;
}

interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];  // 引用的chunk位置
  created_at: Date;
}
```

### 9.3 聊天历史 UI

```tsx
// 右侧 RAG 面板顶部：历史会话列表
<div class="chat-history-sidebar">
  <div class="chat-history-header">
    <span>问答历史</span>
    <button class="btn-ghost btn-icon" aria-label="新建问答" title="新建问答">
      <PlusIcon />
    </button>
  </div>
  <ul class="chat-history-list" role="list">
    {sessions.map(session => (
      <li key={session.id}>
        <button
          class={`chat-session-item ${session.id === activeId ? 'active' : ''}`}
          aria-current={session.id === activeId}
        >
          <HistoryIcon />
          <span>{session.title}</span>
        </button>
      </li>
    ))}
  </ul>
</div>
```

```css
.chat-session-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  color: var(--ink-500);
  text-align: left;
  cursor: pointer;
  transition: all var(--duration-fast) ease;
  overflow: hidden;
  white-space: nowrap;
}

.chat-session-item span {
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-session-item:hover {
  background: var(--paper-gray);
  color: var(--ink-700);
}

.chat-session-item.active {
  background: rgba(58, 107, 196, 0.08);
  color: var(--accent-secondary);
}
```

---

## 10. 动效总表（v4.0 最终版）

| 动效名称 | 参数 | 降级 |
|---------|------|------|
| `card-hover` | translateY(-2px), 220ms | 无 |
| `card-active` | scale(0.99), 50ms | 无 |
| `card-drag` | scale(1.025) rotate(0.8deg), 220ms, ease-spring | transform:none |
| `card-placeholder` | border:dashed, pulse, 1s | 静态虚线框 |
| `btn-press` | translateY(1px), 50ms | 无 |
| `btn-loading` | spinner, 0.7s线性 | 显示静态图标 |
| `fade-in` | opacity 0→1, 220ms | 无 |
| `slide-up` | opacity+translateY, 220ms | opacity直接显示 |
| `list-stagger` | 每项+60ms延迟, 380ms | 无stagger |
| `bubble-in` | opacity+scale, 200ms | opacity直接显示 |
| `typewriter` | 每字20ms | 直接显示全文 |
| `loading-pulse` | 圆点跳动, 300ms | 静态三个点 |
| `progress-fill` | width过渡 | 无动画 |
| `ripple` | scale 0→40x, 450ms | 无 |
| `toast-in` | translateX(120%), 220ms, ease-spring | translateX(120%) |
| `toast-out` | translateX(120%), 180ms | translateX(120%) |
| `batch-toolbar-in` | translateY(-100%), 220ms | 无动效 |
| `skeleton-shimmer` | background-position, 1.5s | 静态灰块 |
| `tooltip-in` | opacity+translateY, 120ms | opacity直接显示 |
| `context-menu-in` | opacity+scale+translateY, 220ms, ease-spring | opacity直接显示 |
| `page-enter` | opacity+translateX, 220ms, ease-out-expo | opacity直接显示 |

---

## 11. 设计原则总结（v4.0）

| 原则 | 具体做法 |
|-----|---------|
| **材质感** | 纸张纹理（静态SVG）、微阴影层次、边框光泽、磨砂玻璃（仅固定元素） |
| **安静** | 克制配色、留白充足、动效轻柔（220ms为主） |
| **精准** | 4px基础单位网格、精确间距层级 |
| **Dark Mode** | 完整墨蓝夜色，色值单独定义 |
| **色盲安全** | 状态 = 颜色 + 图标 + 文字，缺一不可；紫色替代危险红 |
| **系统主题** | `prefers-color-scheme` 自动监听 |
| **对比度合规** | 所有文字组合通过 WCAG AA |
| **语义色分离** | `color-danger`(紫色) ≠ `color-error`(红) ≠ `color-success`(蓝) |
| **按钮体系** | Primary / Secondary / Ghost / Outline / Danger + 加载态 + 禁用态 |
| **表单验证** | error态：边框变色 + 抖动动画 + 文字提示 |
| **补全组件** | Toast / Tooltip / Scrollbar / Context Menu / Tag / Badge / Input变体(search/textarea) |
| **空状态** | 5种场景（无论文/无结果/空收藏夹(仅Phase 2+)/空聊天/空标签）+ 统一结构 + 插画规范 |
| **网络异常** | Toast(局部) / 错误卡片(页面) / 全屏服务不可用页 / 限流提示 / 离线横幅 |
| **页面转场** | 路由切换 220ms slide + fade，不同事由不同方向 |
| **面包屑** | aria-label + aria-current 完整标注 |
| **Micro-copy** | 动词驱动/肯定句/具体/冷静，不废话不甩锅 |
| **聊天历史** | PostgreSQL持久化，50轮上限，多端同步 Phase 2 再做 |
| **无障碍** | focus-visible / reduced-motion / ARIA / WCAG AA / skip link / live regions |
| **中文适配** | 系统中文字体栈 |
| **性能约束** | 列表禁用毛玻璃、静态纹理、无连续repaint动画 |

---

> 文件版本记录
> - v1.0 (17:27): 初始版本 — 材质系统、动效库、组件、页面布局
> - v2.0 (17:40): 优化版 — Dark Mode、Accessibility、中文适配、批量选择、GPU优化、性能预算
> - v3.0 (17:46): 深度优化 — 对比度修复、语义色分离、按钮体系、Toast/Tooltip/Scrollbar/Drag占位、动效精调
> - **v4.0 (17:51): 体验完整版 — 色盲安全(Context Menu三色分离)、图标按钮无障碍(tooltip+aria)、空状态体系(5种)、网络异常态(3级)、页面转场动画、面包屑、Input变体(search/textarea)、Micro-copy指南、通知徽章、Tag组件、聊天历史持久化**
> - **v4.1 (21:28): 与 CEO v2.0 对齐 — 新增功能范围定义表（✅ MVP / ❌ Phase 2+ / ❌ 不做），收藏夹相关功能和空状态标注为 Phase 2+，Context Menu "添加到收藏夹" 标注为 MVP 外**
