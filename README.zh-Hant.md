<p align="center">
  <img src="apps/web/src/assets/images/logo.png" alt="AI 圖片創作工作台 logo" width="160" />
</p>

<h1 align="center">AI 圖片創作工作台</h1>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <strong>繁體中文</strong> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a>
</p>

**AI 圖片創作工作台（Visual Workbench）** 是一個面向攝影創作的開源圖片工作台，將照片管理、本地調色、風格化處理與 AI 輔助創作結合在一起。產品圍繞攝影師的實際工作流程設計：匯入照片、篩選整理、完成可撤銷的基礎調色、保存風格，並在需要時調用 AI。

工作台包含以下相互配合的模式：

- **照片庫** — 匯入照片，按檔案名稱或客戶回饋 ID 搜尋，管理 RAW/JPG 配對，並按格式和選取狀態篩選。
- **基礎調色** — 調整曝光、對比度、飽和度、色溫、色調等參數，並即時預覽結果。
- **色彩匹配與風格化** — 使用參考圖進行色彩匹配，套用 LUT 和可重複使用的風格預設。
- **AI Agent** — 分析照片、拆解需求，並將任務交給本地處理或已配置的 AI 模型。
- **Editor** — 對局部區域添加標記和精確指令，在分析後進行針對性修改。

產品的目標是讓常規攝影工作快速、可控，讓 AI 操作可追蹤、可撤銷。應用支援瀏覽器運行，也可以透過 Electron 打包為桌面應用；FastAPI 後端負責工作區、圖片處理和 AI 編排。

開源。注重隱私。支援 Web、桌面應用、Docker 多種部署方式。

## 快速開始

### 前置需求

- **Python 3.11+** 和 [uv](https://docs.astral.sh/uv/)（Python 套件管理器）
- **Node.js 20+** 和 [pnpm](https://pnpm.io/)（JavaScript 套件管理器）

### 執行

```bash
# 安裝所有依賴（前端 + 後端）
make setup

# 啟動開發伺服器，訪問 http://localhost:8000
make serve
```

前端由後端提供服務，無需單獨的前端開發伺服器。程式碼變更會自動觸發重新建置和瀏覽器重新整理。

## 專案結構

```text
.
├── apps/
│   ├── api/                  # Python FastAPI 後端（uv + litellm）
│   │   ├── src/
│   │   │   ├── main.py       # 應用工廠、中介軟體、靜態檔案服務
│   │   │   ├── config.py     # 設定（Pydantic Settings）
│   │   │   ├── livereload.py # 開發模式熱重載（watchfiles + SSE）
│   │   │   ├── routers/      # HTTP 路由
│   │   │   │   ├── health.py     # GET /health
│   │   │   │   ├── agent.py      # POST /api/v1/agent/run（串流）
│   │   │   │   ├── editor.py     # POST /api/v1/editor/run
│   │   │   │   ├── settings.py   # GET/PUT/DELETE /api/v1/settings
│   │   │   │   └── workspaces.py # CRUD /api/v1/workspaces
│   │   │   ├── core/         # 核心業務邏輯
│   │   │   │   ├── orchestration.py  # Agent & Editor 工作流程
│   │   │   │   ├── analysis.py      # Agent 輸出 JSON 解析
│   │   │   │   ├── prompts.py       # AI 模型提示詞
│   │   │   │   └── types.py         # 資料型別定義
│   │   │   ├── services/     # 外部服務客戶端
│   │   │   │   ├── ai_client.py     # litellm 整合
│   │   │   │   └── image_utils.py   # Pillow 影像處理
│   │   │   └── models/       # 資料模型與 Schema
│   │   │       ├── settings.py  # SQLModel（AppConfig, WorkspaceRecord）
│   │   │       └── schemas.py   # Pydantic 請求/回應模型
│   │   ├── Dockerfile        # 多階段 Docker 建置
│   │   └── run.py            # PyInstaller 進入點
│   └── web/                  # Vue 3 + Vite + Tailwind CSS 前端
│       └── src/
│           ├── views/        # HomeView, WorkspaceView, SettingsView
│           ├── components/   # TopBar, TabBar, Sidebar, ImageViewport 等
│           ├── lib/          # API 客戶端、工作區狀態、設定儲存
│           ├── types/        # TypeScript 型別定義
│           ├── i18n/         # 國際化（5 種語言）
│           └── assets/       # Logo、樣式
├── electron/                 # 桌面應用（Electron + electron-builder）
│   ├── main.js               # 主程序（後端生命週期、視窗管理）
│   ├── preload.js            # contextBridge IPC
│   └── package.json          # electron-builder 設定（macOS/Win/Linux）
├── scripts/                  # 建置與工具腳本
│   ├── serve.py              # 開發伺服器編排
│   ├── setup.py              # 依賴安裝
│   ├── build-desktop.py      # PyInstaller + electron-builder 流水線
│   ├── generate-icons.py     # 從 Logo 產生 .icns/.ico
│   └── banner.py             # ASCII 啟動橫幅
├── docker-compose.yml        # 一鍵 Docker 部署
└── Makefile                  # 常用命令
```

## 功能特性

- **兩種編輯模式** — Agent（自然語言）和 Editor（區域標記）
- **AI 提供商靈活切換** — 支援 OpenRouter、Gemini 及任意 OpenAI 相容 API
- **即時串流回應** — Agent 進度透過 NDJSON 流推送
- **影像處理** — 自動縮放、壓縮、標註渲染（Pillow）
- **工作區管理** — 多專案支援，可儲存/載入/刪除
- **影像歷史** — 支援復原編輯
- **桌面應用** — Electron 封裝，自訂標題列，跨平台安裝套件
- **Docker 支援** — 單容器部署，持久化儲存
- **國際化** — 英文、簡體中文、繁體中文、日語、韓語
- **深色/淺色主題** — 在設定中切換
- **隱私保護** — AI API 呼叫透過自有後端代理，API Key 儲存在本地

## 架構

```
┌─────────────────────────────────────────────────────┐
│                  瀏覽器 / Electron                   │
│  ┌───────────────────────────────────────────────┐  │
│  │         Vue 3 + Vite + Tailwind CSS            │  │
│  │          （純 UI 層，不含業務邏輯）               │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ HTTP / NDJSON 流             │
├──────────────────────┼──────────────────────────────┤
│               FastAPI 後端（單一埠 8000）              │
│  ┌───────────────────┴───────────────────────────┐  │
│  │  路由 → 核心（編排 + 提示詞）                     │  │
│  │  ↓                                            │  │
│  │  服務（litellm → AI 提供商）                    │  │
│  │  模型（SQLite 透過 SQLModel）                   │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## 設定

### API Key

在 `apps/api/.env` 中設定 AI 提供商 API Key（也可在執行時從前端傳入）：

```bash
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...
```

所有 Key 皆為可選——若未設定，前端會提示使用者輸入。

### 後端設定

編輯 `apps/api/.env` 或設定環境變數：

```bash
HOST=0.0.0.0        # 綁定位址（預設: 0.0.0.0）
PORT=8000           # 埠號（預設: 8000）
DOUSHABAO_DATA_DIR=/path/to/data  # 資料目錄覆蓋（用於 Docker）
```

## Docker 部署

```bash
# 使用 Docker Compose 啟動（前景）
docker compose up

# 背景執行
docker compose up -d

# 停止
docker compose down

# 檢視日誌
docker compose logs -f
```

容器在 8000 埠同時提供前端和 API 服務，透過 Docker 磁碟區實現持久化儲存。

## 桌面應用

建置跨平台桌面安裝套件：

```bash
# 建置目前平台
make build-desktop

# 建置指定平台
make build-desktop-mac      # macOS DMG
make build-desktop-win      # Windows NSIS
make build-desktop-linux    # Linux AppImage/deb
make build-desktop-all      # 所有平台

# 僅打包後端（不產生安裝套件）
make build-api
```

桌面應用打包內容：
- **Python 後端** 透過 PyInstaller 打包為獨立可執行檔
- **Vue 前端** 作為靜態檔案
- **Electron** 負責視窗管理和原生功能

## 開發

### 常用命令

```bash
# 安裝依賴
make setup

# 啟動開發伺服器（自動重載）
make serve

# 僅建置前端
make build

# 執行後端測試
cd apps/api && uv run pytest

# 執行前端測試
cd apps/web && pnpm test:unit

# 前端程式碼檢查
cd apps/web && pnpm lint
```

### 開發伺服器詳解

`make serve` 執行單一程序（`python scripts/serve.py`），執行以下操作：

1. 背景啟動 `vite build --watch`（首次建置 + 增量重建）
2. 等待首次建置完成
3. 在 8000 埠啟動 `uvicorn --reload`
4. 前端重新編譯後自動重新整理瀏覽器（透過 SSE 熱重載）

### 架構說明

所有業務邏輯位於 `apps/api/src/core/` 中，前端（`apps/web/`）是純粹的 UI 層。型別定義位於 `apps/web/src/types/`。後端透過 **litellm** 將請求路由到不同的 AI 提供商，支援 OpenRouter、Gemini 和任意 OpenAI 相容 API。

## 授權條款

本專案採用 [MIT License](LICENSE) 授權。
