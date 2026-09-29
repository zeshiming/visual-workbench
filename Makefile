.PHONY: serve setup build build-api build-desktop build-desktop-mac build-desktop-win build-desktop-linux docker-up docker-up-d docker-down docker-logs docker-build docker-ps

# Install all dependencies (frontend + backend)
setup:
	uv sync --directory apps/api && pnpm install

# Start the integrated dev server (http://localhost:8000)
# Vite build --watch rebuilds frontend on changes (no HMR, just refresh)
# Backend serves both API and frontend SPA on a single port
serve:
	python scripts/serve.py

# Build the frontend for production
build:
	@python scripts/banner.py
	cd apps/web && pnpm build

# Start the backend dev server with hot-reload only (no frontend build)
serve-api:
	cd apps/api && uv run python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# ── Desktop App Build ────────────────────────────────────────────

# Package only the Python backend as a standalone executable
build-api:
	python scripts/build-desktop.py --skip-frontend --skip-electron

# Build the desktop app for the current platform
build-desktop:
	python scripts/build-desktop.py

# Build the desktop app (macOS DMG)
build-desktop-mac:
	python scripts/build-desktop.py --mac

# Build the desktop app (Windows NSIS)
build-desktop-win:
	python scripts/build-desktop.py --win

# Build the desktop app (Linux AppImage/deb)
build-desktop-linux:
	python scripts/build-desktop.py --linux

# Build desktop installers for all platforms
build-desktop-all:
	python scripts/build-desktop.py --all

# ── Docker Quick Deploy ─────────────────────────────────────────

# Build and start Docker containers (foreground; Ctrl+C to stop)
docker-up:
	docker compose up

# Build and start Docker containers (detached daemon mode)
docker-up-d:
	docker compose up -d

# Stop Docker containers
docker-down:
	docker compose down

# Tail Docker container logs
docker-logs:
	docker compose logs -f

# Rebuild Docker images only (without starting containers)
docker-build:
	docker compose build

# Check running status
docker-ps:
	docker compose ps
