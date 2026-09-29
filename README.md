<p align="center">
  <img src="apps/web/src/assets/images/logo.png" alt="Doushabao logo" width="160" />
</p>

<h1 align="center">Doushabao</h1>

<p align="center">
  <strong>English</strong> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.zh-Hant.md">繁體中文</a> ·
  <a href="README.ja.md">日本語</a> ·
  <a href="README.ko.md">한국어</a>
</p>

**Doushabao** _(Chinese: 豆沙包 — a sweet red-bean bun)_ is an open-source, browser-based AI image editor. Like its mascot — a cheerful steamed bun with a bite taken out to reveal rich red-bean filling — the app is warm, approachable, and focused on what matters: making your images better, one edit at a time.

Built for creators who want powerful AI editing without a heavy desktop workflow, Doushabao runs entirely in the browser and offers two complementary modes:

- **Agent mode** — describe what you want in natural language; the AI analyzes your image and applies intelligent edits automatically.
- **Editor mode** — mark regions on the canvas and give precise, localized instructions for fine-grained control.

Whether you are retouching a photo, cleaning up distractions, or refining details, Doushabao keeps the process simple: open an image, edit with AI, and export the result — all in a clean, workspace-driven interface.

Open source. Privacy-friendly. Multiple deployment options: web, desktop, or Docker.

## Quick Start

### Prerequisites

- **Python 3.11+** and [uv](https://docs.astral.sh/uv/) (Python package manager)
- **Node.js 20+** and [pnpm](https://pnpm.io/) (JavaScript package manager)

### Run

```bash
# Install all dependencies (frontend + backend)
make setup

# Start the dev server at http://localhost:8000
make serve
```

The frontend is served by the backend — no separate dev server needed. Code changes trigger automatic rebuild and browser reload.

## Project Structure

```text
.
├── apps/
│   ├── api/                  # Python FastAPI backend (uv + litellm)
│   │   ├── src/
│   │   │   ├── main.py       # App factory, middleware, static file serving
│   │   │   ├── config.py     # Pydantic Settings (host, port, API keys)
│   │   │   ├── livereload.py # Dev live-reload via watchfiles + SSE
│   │   │   ├── routers/      # HTTP endpoints
│   │   │   │   ├── health.py     # GET /health
│   │   │   │   ├── agent.py      # POST /api/v1/agent/run (streaming)
│   │   │   │   ├── editor.py     # POST /api/v1/editor/run
│   │   │   │   ├── settings.py   # GET/PUT/DELETE /api/v1/settings
│   │   │   │   └── workspaces.py # CRUD /api/v1/workspaces
│   │   │   ├── core/         # Business logic
│   │   │   │   ├── orchestration.py  # Agent & Editor workflows
│   │   │   │   ├── analysis.py      # JSON parsing of agent output
│   │   │   │   ├── prompts.py       # System prompts for AI models
│   │   │   │   └── types.py         # Data type definitions
│   │   │   ├── services/     # External service clients
│   │   │   │   ├── ai_client.py     # litellm integration
│   │   │   │   └── image_utils.py   # Pillow image processing
│   │   │   └── models/       # Data models & schemas
│   │   │       ├── settings.py  # SQLModel (AppConfig, WorkspaceRecord)
│   │   │       └── schemas.py   # Pydantic request/response models
│   │   ├── Dockerfile        # Multi-stage Docker build
│   │   └── run.py            # PyInstaller entry point
│   └── web/                  # Vue 3 + Vite + Tailwind CSS frontend
│       └── src/
│           ├── views/        # HomeView, WorkspaceView, SettingsView
│           ├── components/   # TopBar, TabBar, Sidebar, ImageViewport, etc.
│           ├── lib/          # API client, workspace state, config storage
│           ├── types/        # TypeScript type definitions
│           ├── i18n/         # Internationalization (5 languages)
│           └── assets/       # Logo, styles
├── electron/                 # Desktop app (Electron + electron-builder)
│   ├── main.js               # Main process (backend lifecycle, window mgmt)
│   ├── preload.js            # contextBridge for IPC
│   └── package.json          # electron-builder config (macOS/Win/Linux)
├── scripts/                  # Build & utility scripts
│   ├── serve.py              # Dev server orchestrator
│   ├── setup.py              # Dependency installer
│   ├── build-desktop.py      # PyInstaller + electron-builder pipeline
│   ├── generate-icons.py     # .icns/.ico from logo
│   └── banner.py             # ASCII banner
├── docker-compose.yml        # One-command Docker deployment
└── Makefile                  # Common commands
```

## Features

- **Two editing modes** — Agent (natural language) and Editor (region-based marks)
- **AI provider flexibility** — OpenRouter, Gemini, and any OpenAI-compatible API
- **Real-time streaming** — Agent progress updates via NDJSON over SSE
- **Image processing** — Automatic resize, compression, and annotation rendering (Pillow)
- **Workspace management** — Multiple projects with save/load/delete
- **Image history** — Undo support for edits
- **Desktop app** — Electron wrapper with custom title bar, cross-platform installers
- **Docker support** — Single-container deployment with persistent storage
- **Internationalization** — English, Simplified Chinese, Traditional Chinese, Japanese, Korean
- **Dark/Light theme** — Toggle via settings
- **Privacy** — All AI API calls are proxied through your own backend; API keys stay on your server

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Browser / Electron                  │
│  ┌───────────────────────────────────────────────┐  │
│  │         Vue 3 + Vite + Tailwind CSS            │  │
│  │   (Pure UI layer — no business logic)          │  │
│  └───────────────────┬───────────────────────────┘  │
│                      │ HTTP / NDJSON Stream         │
├──────────────────────┼──────────────────────────────┤
│         FastAPI Backend (single port 8000)          │
│  ┌───────────────────┴───────────────────────────┐  │
│  │  Routers → Core (orchestration + prompts)     │  │
│  │  ↓                                            │  │
│  │  Services (litellm → AI providers)            │  │
│  │  Models (SQLite via SQLModel)                 │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Agent Workflow

1. Frontend sends image + optional text prompt to `POST /api/v1/agent/run`
2. Backend streams NDJSON events: `progress (analysis)` → `progress (edit)` → `result`
3. Analysis phase: AI model analyzes the image and outputs structured JSON (image type, deficiencies, edit instructions)
4. Edit phase: AI model receives the original image + edit instructions and returns the edited image
5. Frontend receives the result and displays it — all business logic stays on the backend

### Editor Workflow

1. User marks regions on the image canvas (circles with descriptions)
2. Frontend sends image + marks to `POST /api/v1/editor/run`
3. Backend builds the prompt from marks (including pixel coordinates) and calls the AI model
4. Result is returned as a single response

## Configuration

### API Keys

Configure AI provider API keys in `apps/api/.env` (or pass them from the frontend at runtime):

```bash
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=AIza...
OPENAI_API_KEY=sk-...
```

All keys are optional — if unset, the frontend will prompt for them.

### Backend Settings

Edit `apps/api/.env` or set environment variables:

```bash
HOST=0.0.0.0        # Bind address (default: 0.0.0.0)
PORT=8000           # Port (default: 8000)
DOUSHABAO_DATA_DIR=/path/to/data  # Override data directory (for Docker)
```

## Docker Deployment

```bash
# Start with Docker Compose (foreground)
docker compose up

# Or run in background
docker compose up -d

# Stop
docker compose down

# View logs
docker compose logs -f
```

The container serves both the frontend and API on port 8000, with persistent storage via a Docker volume.

## Desktop App

Build cross-platform desktop installers:

```bash
# Build for current platform
make build-desktop

# Build for specific platforms
make build-desktop-mac      # macOS DMG
make build-desktop-win      # Windows NSIS
make build-desktop-linux    # Linux AppImage/deb
make build-desktop-all      # All platforms

# Package backend only (no installer)
make build-api
```

The desktop app bundles:
- **Python backend** via PyInstaller (standalone executable)
- **Vue frontend** as static files
- **Electron** for window management and native features

## Development

### Common Commands

```bash
# Install dependencies
make setup

# Start dev server (auto-reload)
make serve

# Build frontend only
make build

# Run backend tests
cd apps/api && uv run pytest

# Run frontend tests
cd apps/web && pnpm test:unit

# Lint frontend
cd apps/web && pnpm lint
```

### Dev Server Details

`make serve` runs a single process (`python scripts/serve.py`) that:

1. Starts `vite build --watch` in the background (initial build + incremental rebuilds)
2. Waits for the initial build to complete
3. Starts `uvicorn --reload` on port 8000
4. Automatically refreshes the browser when frontend recompiles (via SSE live-reload)

### Architecture Note

All business logic lives in `apps/api/src/core/` — the frontend (`apps/web/`) is a pure UI layer. Type definitions live in `apps/web/src/types/`. The backend uses **litellm** to route requests to different AI providers, supporting OpenRouter, Gemini, and any OpenAI-compatible API.

## License

This project is licensed under the [MIT License](LICENSE).
