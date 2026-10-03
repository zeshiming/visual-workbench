# =============================================================================
# Doushabao AI Image Editor — Docker 多阶段构建
# =============================================================================

# ── Stage 1: 构建前端（Vue 3 + Vite） ──────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /app

# 安装 pnpm
RUN corepack enable && corepack prepare pnpm@10 --activate

# 分离依赖安装层，利用 Docker 层缓存
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml .npmrc ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile

# 构建前端
COPY apps/web/ apps/web/
RUN cd apps/web && pnpm build-only

# ── Stage 2: 后端运行时（Python + FastAPI） ────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# 安装 uv（极速 Python 包管理器）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 复制依赖清单并安装
COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/
RUN uv sync --directory apps/api --no-dev --frozen && \
    rm -rf /root/.cache/uv

# 复制后端源码
COPY apps/api/src/ apps/api/src/

# 复制前端构建产物
COPY --from=frontend-builder /app/apps/web/dist/ apps/web/dist/

# 创建持久化数据目录
RUN mkdir -p /data && \
    chmod 755 /data

EXPOSE 8000

WORKDIR /app/apps/api

ENV DOUSHABAO_DATA_DIR=/data

CMD [".venv/bin/uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
