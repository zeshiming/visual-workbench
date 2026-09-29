<p align="center">
  <img src="apps/web/src/assets/images/logo.png" alt="豆沙包 logo" width="160" />
</p>

<h1 align="center">豆沙包</h1>

<p align="center">
  <a href="README.md">English</a> ·
  <strong>简体中文</strong> ·
  <a href="README.zh-Hant.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a>
</p>

**豆沙包（Doushabao）** 是一款开源、基于浏览器的 AI 图像编辑器。就像它的吉祥物——一只被咬了一口的可爱包子，露出饱满的豆沙馅——应用温暖、易用，专注于一件事：让你的图片更好，一次编辑一点进步。

为希望获得强大 AI 编辑能力、又不想被繁重桌面工作流束缚的创作者而打造，豆沙包完全在浏览器中运行，提供两种互补模式：

- **Agent 模式** — 用自然语言描述你想要的效果；AI 会分析图像并自动应用智能编辑。
- **Editor 模式** — 在画布上标记区域，给出精确、局部的指令，实现细粒度控制。

无论是修图、去除干扰物还是打磨细节，豆沙包都让流程保持简单：打开图片、用 AI 编辑、导出结果——一切都在简洁的工作区界面中完成。

开源。注重隐私。支持 Web、桌面应用、Docker 多种部署方式。

## 快速开始

### 前置要求

- **Python 3.11+** 和 [uv](https://docs.astral.sh/uv/)（Python 包管理器）
- **Node.js 20+** 和 [pnpm](https://pnpm.io/)（JavaScript 包管理器）

### 运行

```bash
# 安装所有依赖（前端 + 后端）
make setup

# 启动开发服务器，访问 http://localhost:8000
make serve
```

前端由后端提供服务，无需单独的前端开发服务器。代码变更会自动触发重新构建和浏览器刷新。

## 项目结构

```text
.
├── apps/
│   ├── api/                  # Python FastAPI 后端（uv + litellm）
│   │   ├── src/
│   │   │   ├── main.py       # 应用工厂、中间件、静态文件服务
│   │   │   ├── config.py     # 配置（Pydantic Settings）
│   │   │   ├── livereload.py # 开发模式热重载（watchfiles + SSE）
│   │   │   ├── routers/      # HTTP 路由
│   │   │   │   ├── health.py     # GET /health
│   │   │   │   ├── agent.py      # POST /api/v1/agent/run（流式）
│   │   │   │   ├── editor.py     # POST /api/v1/editor/run
│   │   │   │   ├── settings.py   # GET/PUT/DELETE /api/v1/settings
│   │   │   │   └── workspaces.py # CRUD /api/v1/workspaces
│   │   │   ├── core/         # 核心业务逻辑
│   │   │   │   ├── orchestration.py  # Agent & Editor 工作流
│   │   │   │   ├── analysis.py      # Agent 输出 JSON 解析
│   │   │   │   ├── prompts.py       # AI 模型提示词
│   │   │   │   └── types.py         # 数据类型定义
│   │   │   ├── services/     # 外部服务客户端
│   │   │   │   ├── ai_client.py     # litellm 集成
│   │   │   │   └── image_utils.py   # Pillow 图像处理
│   │   │   └── models/       # 数据模型与 Schema
│   │   │       ├── settings.py  # SQLModel（AppConfig, WorkspaceRecord）
│   │   │       └── schemas.py   # Pydantic 请求/响应模型
│   │   ├── Dockerfile        # 多阶段 Docker 构建
│   │   └── run.py            # PyInstaller 入口
│   └── web/                  # Vue 3 + Vite + Tailwind CSS 前端
│       └── src/
│           ├── views/        # HomeView, WorkspaceView, SettingsView
│           ├── components/   # TopBar, TabBar, Sidebar, ImageViewport 等
│           ├── lib/          # API 客户端、工作区状态、配置存储
│           ├── types/        # TypeScript 类型定义
│           ├── i18n/         # 国际化（5 种语言）
│           └── assets/       # Logo、样式
├── electron/                 # 桌面应用（Electron + electron-builder）
│   ├── main.js               # 主进程（后端生命周期、窗口管理）
│   ├── preload.js            # contextBridge IPC
│   └── package.json          # electron-builder 配置（macOS/Win/Linux）
├── scripts/                  # 构建与工具脚本
│   ├── serve.py              # 开发服务器编排
│   ├── setup.py              # 依赖安装
│   ├── build-desktop.py      # PyInstaller + electron-builder 流水线
│   ├── generate-icons.py     # 从 Logo 生成 .icns/.ico
│   └── banner.py             # ASCII 启动横幅
├── docker-compose.yml        # 一键 Docker 部署
└── Makefile                  # 常用命令
```

## 功能特性

- **两种编辑模式** — Agent（自然语言）和 Editor（区域标记）
- **AI 提供商灵活切换** — 支持 OpenRouter、Gemini 及任意 OpenAI 兼容 API
- **实时流式响应** — Agent 进度通过 NDJSON 流推送
- **图像处理** — 自动缩放、压缩、标注渲染（Pillow）
- **工作区管理** — 多项目支持，可保存/加载/删除
- **图像历史** — 支持撤销编辑
- **桌面应用** — Electron 封装，自定义标题栏，跨平台安装包
- **Docker 支持** — 单容器部署，持久化存储
- **国际化** — 英文、简体中文、繁体中文、日语、韩语
- **深色/浅色主题** — 在设置中切换
- **隐私保护** — AI API 调用通过自有后端代理，API Key 保存在本地

## 架构

```
┌─────────────────────────────────────────────────────┐
│                  浏览器 / Electron                   │
│  ┌───────────────────────────────────────────────┐  │
│  │         Vue 3 + Vite + Tailwind CSS            │  │
│  │          （纯 UI 层，不含业务逻辑）               │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ HTTP / NDJSON 流             │
├──────────────────────┼──────────────────────────────┤
│               FastAPI 后端（单端口 8000）              │
│  ┌───────────────────┴───────────────────────────┐  │
│  │  路由 → 核心（编排 + 提示词）                     │  │
│  │  ↓                                            │  │
│  │  服务（litellm → AI 提供商）                    │  │
│  │  模型（SQLite 通过 SQLModel）                   │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Agent 工作流

1. 前端将图片和可选文本提示发送到 `POST /api/v1/agent/run`
2. 后端流式推送 NDJSON 事件：`progress (analysis)` → `progress (edit)` → `result`
3. 分析阶段：AI 模型分析图片并输出结构化 JSON（图片类型、缺陷、编辑指令）
4. 编辑阶段：AI 模型接收原始图片 + 编辑指令，返回修图结果
5. 前端接收结果显示——所有业务逻辑保留在后端

### Editor 工作流

1. 用户在图片画布上标记区域（带描述的圆圈）
2. 前端将图片 + 标记发送到 `POST /api/v1/editor/run`
3. 后端根据标记构建提示词（包含像素坐标），调用 AI 模型
4. 结果以单次响应返回

## 配置

### API Key

在 `apps/api/.env` 中配置 AI 提供商 API Key（也可在运行时从前端传入）：

```bash
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...
```

所有 Key 均为可选——若未配置，前端会提示用户输入。

### 后端设置

编辑 `apps/api/.env` 或设置环境变量：

```bash
HOST=0.0.0.0        # 绑定地址（默认: 0.0.0.0）
PORT=8000           # 端口（默认: 8000）
DOUSHABAO_DATA_DIR=/path/to/data  # 数据目录覆盖（用于 Docker）
```

## Docker 部署

```bash
# 使用 Docker Compose 启动（前台）
docker compose up

# 后台运行
docker compose up -d

# 停止
docker compose down

# 查看日志
docker compose logs -f
```

容器在 8000 端口同时提供前端和 API 服务，通过 Docker 卷实现持久化存储。

## 桌面应用

构建跨平台桌面安装包：

```bash
# 构建当前平台
make build-desktop

# 构建指定平台
make build-desktop-mac      # macOS DMG
make build-desktop-win      # Windows NSIS
make build-desktop-linux    # Linux AppImage/deb
make build-desktop-all      # 所有平台

# 仅打包后端（不生成安装包）
make build-api
```

桌面应用打包内容：
- **Python 后端** 通过 PyInstaller 打包为独立可执行文件
- **Vue 前端** 作为静态文件
- **Electron** 负责窗口管理和原生功能

## 开发

### 常用命令

```bash
# 安装依赖
make setup

# 启动开发服务器（自动重载）
make serve

# 仅构建前端
make build

# 运行后端测试
cd apps/api && uv run pytest

# 运行前端测试
cd apps/web && pnpm test:unit

# 前端代码检查
cd apps/web && pnpm lint
```

### 开发服务器详解

`make serve` 运行单个进程（`python scripts/serve.py`），执行以下操作：

1. 后台启动 `vite build --watch`（首次构建 + 增量重建）
2. 等待首次构建完成
3. 在 8000 端口启动 `uvicorn --reload`
4. 前端重新编译后自动刷新浏览器（通过 SSE 热重载）

### 架构说明

所有业务逻辑位于 `apps/api/src/core/` 中，前端（`apps/web/`）是纯粹的 UI 层。类型定义位于 `apps/web/src/types/`。后端通过 **litellm** 将请求路由到不同的 AI 提供商，支持 OpenRouter、Gemini 和任意 OpenAI 兼容 API。

## 许可证

本项目采用 [MIT License](LICENSE) 授权。
