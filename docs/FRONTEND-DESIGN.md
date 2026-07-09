 # Frontend Design System
 
 > 铸造行业材料知识库 AI 助手 — 前端设计文档
 > 版本：v0.2 | 更新日期：2026-07-09
 
 ---
 
 ## 一、设计理念
 
 ### Precision Industrial（精密工业）
 
 本产品的视觉设计围绕 **精密工业** 展开。这不是一个通用的 SaaS 工具，而是一个面向铸造/金属加工领域工程师的专业知识库。设计语言借鉴了：
 
 - **工程图纸与坐标纸** — 欢迎页的极淡网格底纹
 - **金属与高温材质** — 铜色（bronze/copper）主色调替代标准 SaaS 蓝
 - **精密仪器** — 克制的间距系统、统一圆角、细腻阴影
 - **专业工具** — 所有交互元素具备完整状态覆盖（hover/focus/active/disabled/loading）
 
 ### 设计原则（基于 Impeccable Product Register）
 
 1. **Restrained Color Strategy** — 单色铜色 accent，语义色仅用于状态指示
 2. **One Family Typography** — 系统字体单一家族，无需 display/body 配对
 3. **Motion Conveys State** — 150-200ms 过渡，动效仅用于状态变化（hover/focus/active），无装饰性动画
 4. **Earned Familiarity** — 组件词汇一致，不发明奇怪的手势或控件
 5. **State-rich Vocabulary** — 每个交互组件都有 default/hover/focus/active/disabled/loading
 
 ### AI Slop Test 合规
 
 - ✅ 无渐变文字（background-clip: text）
 - ✅ 无毛玻璃/模糊作为装饰
 - ✅ 无 side-stripe 边框作为唯一区分
 - ✅ 无英雄指标模板（大数字+小标签）
 - ✅ 无彩虹色/脉冲动画的进度条
 - ✅ 无装饰性 SVG 插画
 - ✅ 无重复的 section eyebrow（小写跟踪标题）
 - ✅ 无 01/02/03 编号标记作为默认脚手架
 - ✅ 无幽灵卡片（border + 宽 shadow 同时用）
 - ✅ 无过度圆角（card border-radius ≤ 10px）
 
 ---
 
 ## 二、设计令牌（Design Tokens）
 
 ### 2.1 色彩体系
 
 主色调选择铜色（bronze），而非标准 SaaS 蓝色。铜色与铸造/金属加工行业的材料语境直接关联。
 
 #### Light Theme
 
 | Token | 值 | 用途 |
 |-------|-----|------|
 | `--bg` | `#f4f2ef` | 页面背景（暖灰白） |
 | `--bg-surface` | `#ffffff` | 表面/卡片背景 |
 | `--bg-sidebar` | `#edebe8` | 侧栏背景 |
 | `--bg-hover` | `#e3e0dc` | 悬浮态背景 |
 | `--bg-user` | `#CD7F32` | 用户消息气泡，accent |
 | `--bg-assistant` | `#ffffff` | AI 消息气泡 |
 | `--bg-code` | `#edebe8` | 行内代码背景 |
 | `--text-primary` | `#1c1b1a` | 主要文字 |
 | `--text-secondary` | `#78736c` | 次要文字 |
 | `--border` | `#ddd9d4` | 边框 |
 | `--accent` | `#CD7F32` | 主强调色（铜色） |
 | `--accent-hover` | `#b86d25` | 强调色悬浮 |
 | `--accent-light` | `#faf0e6` | 强调色浅色底 |
 
 #### Dark Theme
 
 | Token | 值 | 用途 |
 |-------|-----|------|
 | `--bg` | `#131211` | 页面背景（深炭色） |
 | `--bg-surface` | `#1c1b19` | 表面/卡片背景 |
 | `--bg-sidebar` | `#181715` | 侧栏背景 |
 | `--bg-hover` | `#282623` | 悬浮态背景 |
 | `--bg-user` | `#D4956A` | 用户消息气泡 |
 | `--bg-assistant` | `#22211e` | AI 消息气泡 |
 | `--border` | `#34322e` | 边框 |
 | `--text-primary` | `#e8e6e3` | 主要文字 |
 | `--text-secondary` | `#8a857e` | 次要文字 |
 | `--accent` | `#D4956A` | 主强调色（暖铜色） |
 
 #### Semantic 语义色
 
 | 用途 | Light | Dark |
 |------|-------|------|
 | Error | `#dc2626` | `#ef4444` |
 | Success | `#10b981` | `#34d399` |
 | Warning | `#d97706` | `#f59e0b` |
 | Danger text | `#dc2626` | — |
 | Danger hover bg | `rgba(239,68,68,0.08)` | — |
 
 ### 2.2 字号刻度
 
 | Token | 值 | 用途 |
 |-------|-----|------|
 | `--text-xs` | `0.75rem` (12px) | 徽章、次级状态 |
 | `--text-sm` | `0.8125rem` (13px) | 正文、侧栏项 |
 | `--text-base` | `0.875rem` (14px) | 消息、输入框 |
 | `--text-lg` | `1rem` (16px) | 标题 |
 | `--text-xl` | `1.25rem` (20px+) | 大标题/欢迎页 |
 
 ### 2.3 间距系统
 
 间距遵循 4px 递增网格：
 
 | 层级 | 值 | 典型用途 |
 |------|-----|---------|
 | 2px | `2px` | 图标按钮间距 |
 | 4px | `4px` | 分组内间距 |
 | 8px | `8px` | 元素间间距 |
 | 12px | `12px` | 消息间距 |
 | 16px | `16px` | 区块间距、内边距 |
 | 20px | `20px` | 大区块间距 |
 | 24px | `24px` | 消息区域边距 |
 | 32px | `32px` | 模态框内边距 |
 
 ### 2.4 圆角系统
 
 | Token | 值 | 用途 |
 |-------|-----|------|
 | `--radius-sm` | `6px` | 按钮、控件、徽章 |
 | `--radius` | `10px` | 面板、卡片、模态框 |
 | border-radius | `6px` | 图标按钮、头像 |
 | border-radius | `8px` | 侧栏搜索输入框 |
 | border-radius | `20px` | 建议标签、头像按钮 |
 
 ### 2.5 阴影系统
 
 | Token | Light | Dark | 用途 |
 |-------|-------|------|------|
 | `--shadow` | `0 1px 2px rgba(0,0,0,0.05)` | `0 1px 3px rgba(0,0,0,0.3)` | 消息气泡 |
 | `--shadow-lg` | `0 4px 12px rgba(0,0,0,0.07)` | `0 4px 12px rgba(0,0,0,0.4)` | 下拉菜单、模态框 |
 
 ### 2.6 Z-index 刻度
 
 | Token | 值 | 用途 |
 |-------|-----|------|
 | `--z-dropdown` | 100 | 用户下拉菜单 |
 | `--z-sticky` | 200 | 粘性元素 |
 | `--z-modal-backdrop` | 900 | 模态框底层、PDF 查看器 |
 | `--z-modal` | 1000 | 信息模态框 |
 | `--z-toast` | 1100 | Toast 通知 |
 | `--z-tooltip` | 1200 | 提示框 |
 
 ---
 
 ## 三、布局结构
 
 ### 3.1 整体布局
 
 ```
 ┌─────────────────────────────────────────────┐
 │  Top Bar (48px)                              │
 ├──────────┬──────────────────────────────────┤
 │          │  Chat Area                        │
 │ Sidebar  │  ↕ scroll                         │
 │ (240px)  │  ┌──────────────────────────┐     │
 │          │  │ Messages (max 740px)     │     │
 │          │  │                          │     │
 │          │  └──────────────────────────┘     │
 ├──────────┴──────────────────────────────────┤
 │  Input Area (bottom)                         │
 └─────────────────────────────────────────────┘
 ```
 
 - 顶栏高度：48px
 - 侧栏宽度：240px
 - 聊天区高度：`calc(100vh - 48px - 132px)`
 - 消息区居中：`max-width: 740px; margin: 0 auto`
 - 响应式断点：768px 以下隐藏侧栏
 
 ### 3.2 顶栏（Top Bar）
 
 ```
 [Logo] [标题] [模型徽章]               [PDF] [主题] [信息] [用户菜单/登录]
 ```
 
 - Logo：32x32 铜色浅底圆角容器，内含自定义 SVG 坩埚图标
 - 标题：15px semibold，-0.01em 字距
 - 模型徽章：10px，6px 圆角，铜色文字+浅底
 - 图标按钮：32x32，6px 圆角，默认 `--text-secondary`，hover 变 `--text-primary`
 - 底部发光：`inset 0 -1px 0 color-mix(in srgb, var(--accent) 12%, transparent)`
 
 ### 3.3 侧栏（Sidebar）
 
 - 顶部标题栏可放置章节筛选标题 + 清除按钮
 - 搜索输入框独立于章节列表
 - 章节列表支持 3 级深度（data-depth="0/1/2"）
   - depth 0：加粗（600），全宽缩进
   - depth 1：24px 左缩进，12px 字号
   - depth 2：36px 左缩进，11px 字号
 - active 状态：铜色背景 + 白色文字 + 轻微阴影
 - 自定义滚动条（4px 宽，圆角）
 - 底部：知识库概览链接
 
 ### 3.4 聊天区（Chat Area）
 
 消息列表居中：
 - 容器 `max-width: 740px`，`margin: 0 auto`
 - 消息间距 20px
 - 入场动画：`fadeIn`（0.3s，8px 上移+透明度）
 - 自定义滚动条（6px 宽，3px 圆角）
 
 ### 3.5 输入区（Input Area）
 
 - 区域顶部：1px 分隔线
 - 输入框：1.5px 边框，focus 时铜色 + 2px 阴影
 - 发送按钮：铜色背景，600 字重，hover 上移 1px，active 归位
 - 底部提示文字：11px，65% 透明度
 - 自动缩放 textarea（最多 120px 高）
 
 ---
 
 ## 四、组件库
 
 ### 4.1 消息气泡（Message Bubbles）
 
 **用户消息：**
 - 铜色背景 + 白色文字
 - 右下角小圆角（4px 替代 10px）
 - 右侧 3px 半透明铜色竖线
 
 **AI 消息：**
 - 白色（浅色）/ 深色（深色）背景
 - 1px 边框
 - 左下角小圆角
 - 左侧 3px 铜色竖线（accent border）
 - 头像 32px 圆形：用户铜色 / AI 琥珀色
 
 ### 4.2 输入控件
 
 | 控件 | 状态 | 样式 |
 |------|------|------|
 | Input text | default | 1.5px border, 10px radius |
 | Input text | focus | copper border + 2px glow |
 | Input text | placeholder | secondary color, 0.6 opacity |
 | Button | default | copper bg, white text, 6px radius |
 | Button | hover | opacity 0.9, translateY(-1px) |
 | Button | disabled | opacity 0.4 |
 | Button | loading | text hidden, spinner ::after |
 | Auth input | focus | copper border, 3px glow |
 
 ### 4.3 模态框（Modal）
 
 **信息模态框：**
 - 背景模糊 2px
 - 入场动画：`modalSlideUp`（0.2s，16px 上移 + scale 0.97）
 - 420px 宽，90vw 最大
 
 **认证模态框：**
 - 背景模糊 4px
 - 入场动画：`modalSlideUp`（0.25s）
 - 32px 内边距
 - 标签页切换（登录/注册）+ 底部下划线指示
 - OTP 6 位输入框：44x52px，focus 时铜色 + 3px 发光
 - Social 按钮：Google（带 SVG logo）+ GitHub（带 SVG logo）
 - loading spinner 态
 
 ### 4.4 进度步骤条（Progress Steps）
 
 5 步骤水平排列，用于展示 RAG 查询进度：
 
 ```
  🔍 ── 📡 ── 📚 ── 🤖 ── ✅
 分析   检索   精选   生成   检查
 ```
 
 - 每个步骤：28px 圆形图标 + 标签 + 状态文字
 - 步骤之间：20px 连接线
 - 三状态：inactive（0.25 透明度）→ active（铜色边框）→ done（铜色实心）
 - 背景：半透明侧栏色（`color-mix(in srgb, var(--bg-sidebar) 50%, transparent)`）
 - 无脉冲动画，无彩虹色
 
 ### 4.5 日志面板（Log Panel）
 
 - 可折叠，带标题和条数徽章
 - 暗色终端风格背景（#111211 / #f0eeea）
 - Monospace 字体（Cascadia Code → Fira Code → Consolas）
 - 不同日志级别颜色：retry（琥珀）、fallback（橙）、done（绿）、error（红）
 - 行级动画：`logFadeIn`（0.2s，-3px 上移）
 
 ### 4.6 PDF 查看器
 
 - 浮动面板，可拖拽、可缩放（resize: both）
 - 固定定位：top 56px，right 16px，height 70vh
 - 最大化 90vw x 90vh，最小 320x300
 - 入场动画：`pdfFadeIn`（0.25s，scale 0.95 + 10px 上移）
 
 ### 4.7 Toast 通知
 
 - 固定页面底部居中
 - 入场动画：`toastIn`（0.2s，8px 上移）
 - 4 秒自动消失
 - `.toast` 默认状态，`.toast-error` 红色
 - z-index：1100（最顶层）
 
 ### 4.8 用户菜单（User Menu）
 
 - 登录后显示，替代登录按钮
 - 首字母圆形头像（26px，铜色底+白色字）
 - 用户名最多 80px 溢出省略
 - 下拉菜单：200px 宽，平滑浮现动画
 - 内部分隔：用户名 + 邮箱 + 验证状态 + 分割线 + 操作按钮
 - 退出按钮红色 danger 样式
 
 ### 4.9 引用/引用卡（Citations）
 
 - 引用来源以卡片形式展示在 AI 回答下方
 - 卡片包含：页码徽章 + 相关度分数 + 章节名 + 摘要
 - hover 状态：铜色边框 + 浅铜色背景
 
 ---
 
 ## 五、图标系统
 
 所有图标使用 **内联 SVG**（基于 Lucide 图标路径），无外部依赖：
 
 | 位置 | SVG 图标 | 尺寸 |
 |------|---------|------|
 | Logo | 自定义坩埚图标 | 22x22 |
 | PDF 切换 | file-text | 18x18 |
 | 主题切换 | moon / sun | 18x18 |
 | 信息 | info | 18x18 |
 | 登录 | log-in | 18x18 |
 | 侧栏章节 | folder-tree | 16x16 |
 | 全部章节 | files | 14x14 |
 | 知识库概览 | book-open | 14x14 |
 | 欢迎页 | 自定义坩埚图标 | 40x40 |
 | 步骤-分析 | search | 14x14 |
 | 步骤-检索 | radio | 14x14 |
 | 步骤-精选 | book-open | 14x14 |
 | 步骤-生成 | bot | 14x14 |
 | 步骤-检查 | check-circle | 14x14 |
 | 关闭/清除 | x | 12/16/18x |
 
 图标通过 JS 主题切换函数控制 SVG 显隐（moon ↔ sun）。
 
 ---
 
 ## 六、交互与动效
 
 ### 6.1 过渡时间标准
 
 | 类型 | 时长 | 缓动 |
 |------|------|------|
 | Hover 状态 | 100-150ms | ease |
 | Focus/Active | 150-200ms | ease |
 | 入场动画 | 200-300ms | ease |
 | 过渡（色彩/阴影） | 150-200ms | ease |
 | 下拉菜单浮现 | 150ms | ease |
 
 ### 6.2 所有交互状态
 
 | 元素 | default | hover | focus | active | disabled | loading |
 |------|---------|-------|-------|--------|----------|---------|
 | 图标按钮 | secondary color | bg-hover, primary | — | — | — | — |
 | 输入框 | 1.5px border | — | copper + glow | — | — | — |
 | 发送按钮 | copper bg | opacity 0.9, up 1px | — | reset | opacity 0.4 | — |
 | 建议标签 | 1.5px border | copper border, up 1px | — | — | — | — |
 | 引用卡 | border | copper border + bg | — | — | — | — |
 | 认证提交 | copper bg | opacity 0.9, up 1px | — | — | opacity 0.4 | spinner |
 
 ### 6.3 入场动画
 
 - **消息**：`fadeIn` — 0.3s，8px 上移 + 透明度
 - **模态框**：`modalSlideUp` — 0.2-0.25s，16px 上移 + scale 0.97
 - **PDF 查看器**：`pdfFadeIn` — 0.25s，scale 0.95 + 10px 上移
 - **日志条目**：`logFadeIn` — 0.2s，-3px 上移 + 透明度
 - **Toast**：`toastIn` — 0.2s，8px 上移 + 透明度
 
 ---
 
 ## 七、认证系统 UI
 
 ### 7.1 流程
 
 1. 未登录：顶栏显示 🔑 登录按钮
 2. 点击登录 → 弹出认证模态框（登录/注册标签页）
 3. 登录：邮箱 + 密码 → 提交 → 设置 cookie + localStorage
 4. 注册：邮箱 + 用户名 + 密码 → 发送验证码 → OTP 6 位验证 → 完成
 5. Google OAuth：跳转 Google 授权 → 回调 → 设置 cookie → 重定向
 6. 登录后：顶栏显示用户首字母头像 + 用户名
 7. 下拉菜单：用户名 + 邮箱 + 验证状态 + 退出
 
 ### 7.2 Session 持久化
 
 - 登录/注册/Google OAuth 成功后设置 `auth_token` cookie（72 小时）
 - 页面加载时优先检查 URL token（OAuth 回调），然后检查 cookie
 - 退出登录时清除 localStorage 和 cookie
 
 ### 7.3 用户头像
 
 - 自动生成：取用户名首字母大写
 - 26px 圆形，铜色背景 + 白色 11px 700-weight 文字
 - 类似 Gmail/Linear 风格
 
 ---
 
 ## 八、响应式设计
 
 ### 手机端（< 768px）
 
 - 侧栏隐藏（`display: none`）
 - 消息区域 padding 减少（24px → 16px）
 - 欢迎页标题缩小（22px → 18px）
 - 消息气泡全宽（`max-width: 100%`）
 - 输入区底部 flex 换列
 
 ### 平板/桌面（≥ 768px）
 
 - 侧栏固定 240px
 - 消息区 740px 居中
 - 标准间距
 
 ---
 
 ## 九、实现架构
 
 ### 文件结构
 
 ```
 app/
 ├── index.html     # 主页面结构（单页应用）
 ├── style.css      # 全部样式（无框架，纯 CSS Custom Properties）
 └── app.js         # 前端逻辑（无框架，原生 JS）
 ```
 
 ### 技术栈
 
 - **CSS**: 纯 CSS Custom Properties，无预处理器，无框架
 - **Icon**: 内联 SVG（基于 Lucide 路径），无外部依赖
 - **JS**: 原生 JavaScript（ES6+），无框架
 - **Cookie**: 原生 `document.cookie` API
 - **Auth**: JWT + bcrypt（后端），localStorage + Cookie（前端）
 - **SSE**: Server-Sent Events 实时流
 - **Font**: 系统字体栈（-apple-system, Segoe UI, Noto Sans SC）
 
 ### 主题管理
 
 - `data-theme` 属性在 `<html>` 元素上切换 `light`/`dark`
 - 所有颜色通过 CSS Custom Properties 动态切换
 - 主题偏好存储于 `localStorage`
 - 主题切换时 moon/sun SVG 图标通过 JS 控制显隐
 
 ---
 
 ## 十、设计决策记录
 
 ### v0.2（2026-07-09）
 
 | 决策 | 之前 | 之后 | 理由 |
 |------|------|------|------|
 | Accent 色 | 标准蓝 #2563eb | 铜色 #CD7F32 | 铸造行业金属语境 |
 | 背景色 | 冷灰 #f5f5f7 | 暖灰 #f4f2ef | 工业感更温润 |
 | 进度条颜色 | 5 色彩虹 | 单色铜色 | 符合 restrained palette |
 | 进度条动效 | 脉冲发光 | 无动效 | motion conveys state |
 | 头像 | 👤 emoji | 首字母 SVG | 专业感 |
 | 图标 | 系统 emoji | 内联 SVG | 跨平台一致性 |
 | Session | localStorage 仅 | localStorage + Cookie | 跨标签页持久化 |
 | 顶栏高度 | 52px | 48px | 更紧凑 |
 | 侧栏宽度 | 260px | 240px | 更平衡 |
 | 输入框圆角 | 8px | 6px | 统一控件圆角 |
 | 身份验证 | 无界面 | 完整 auth modal | 多用户支持 |
 | Toast | 无样式 | 固定底中弹出 | 用户反馈可见 |
 
 ### v0.1（2026-07-06）
 
 - 初始版本：基础侧栏 + 聊天布局
 - 标准蓝白配色
 - emoji 图标
 - 多 Agent 架构分离（Orchestrator + Search + Generate）
 - SSE 实时日志
