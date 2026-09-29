# Doushabao Project Structure

## Principles

1. **pnpm** manages frontend (JS/TS) dependencies (`apps/web/`)
2. **uv** manages Python backend dependencies (`apps/api/`)
3. Use `make` commands from the project root
4. **AI must not start the dev server**
5. Architecture: Vue frontend (`apps/web/`) → Python FastAPI backend (`apps/api/`) → AI providers (via litellm)
6. All business logic (prompts, AI orchestration, image processing) lives in `apps/api/src/core/` — the frontend is a pure UI layer
7. Type definitions are in `apps/web/src/types/`
8. API keys can be configured via `apps/api/.env` or passed from the frontend
9. Python dependencies are managed by uv (`uv sync --directory apps/api`)

## How It Works

`make serve` starts a single-port dev server (http://localhost:8000):

1. Cleans `apps/web/dist` for a clean initial build
2. `vite build --watch` runs in the background — watches frontend source files
   and auto-rebuilds when they change (no HMR, just refresh the browser)
3. **FastAPI backend** runs via uvicorn `--reload` (port 8000), serving both
   the API and the frontend SPA from `dist/` on a single port

Frontend changes → Vite rebuilds → refresh browser to see updates.
Backend changes → uvicorn auto-restarts.

## Desktop App Architecture

`make build-desktop` packages the web app into cross-platform desktop installers:

```
┌─────────────────────────────────────────┐
│  Electron Window (BrowserWindow)        │
│  ┌───────────────────────────────────┐  │
│  │   Vue Frontend (apps/web/dist/)   │  │
│  │   ← Served by API StaticFiles     │  │
│  └──────────────┬────────────────────┘  │
│                 │ HTTP 127.0.0.1:18xxx  │
│  ┌──────────────▼────────────────────┐  │
│  │   FastAPI Backend (PyInstaller)   │  │
│  │   apps/api/src/ → standalone exe  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

- **Electron** (`electron/`) — window management, process lifecycle, IPC communication
- **PyInstaller** — bundles `apps/api/` into a standalone executable
- **electron-builder** — produces macOS(.dmg) / Windows(.exe) / Linux(.AppImage,.deb) installers
- Backend binds to `127.0.0.1` and auto-selects an available port (starting from 18000)
- User config and database are stored in the system userData directory

## Common Commands

```bash
# Initial setup (install all dependencies)
make setup

# Start the dev server (http://localhost:8000, single-port)
make serve

# Build frontend for production
make build

# Build desktop app (current platform)
make build-desktop

# Package Python backend only (no installer)
make build-api

# Build for specific platforms
make build-desktop-mac     # macOS DMG
make build-desktop-win     # Windows NSIS
make build-desktop-linux   # Linux AppImage/deb
make build-desktop-all     # All platforms
```

## Icons

The desktop icon reuses the project logo (`apps/web/src/assets/images/logo.png`), which is automatically copied to `electron/assets/icon.png` during build.
Running `python scripts/generate-icons.py` can additionally generate `.icns` and `.ico` formats (requires Pillow), but electron-builder can use PNG directly and auto-convert.
