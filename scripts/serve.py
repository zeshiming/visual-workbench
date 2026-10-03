"""
一体化开发服务器 — Vite build watch + FastAPI，单端口。

流程：
  1. 清理前端 dist 目录（确保初始构建干净）
  2. vite build --watch 后台运行（监听前端文件变更，自动增量重构建）
  3. uvicorn 前台运行（单端口 8000，同时提供 API 和前端静态文件）
  4. 前端代码变更 → Vite 自动重构建 → 浏览器刷新即可看到更新
  5. 后端代码变更 → uvicorn --reload 自动重启

注意：
  - 不再使用 Vite dev server，改用 vite build --watch
  - 后端直接提供前端 SPA 文件，所有请求走同一端口
  - 开发时访问 http://localhost:8000
  - 若 dist 中旧 hash 文件累积，重启服务即可清理（Ctrl+C → make serve）
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

BACKEND_PORT = 8000


def _get_lan_ip() -> str | None:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("10.254.254.254", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def _serve_banner(port: int) -> str:
    """Show the single-port dev server URL."""
    lan_ip = _get_lan_ip()

    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    MAGENTA = "\033[35m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    DIM = "\033[2m"

    logo = rf"""{CYAN}{BOLD}
  ___     ___   __ __  _____ __ __   ____  ____    ____   ___ {RESET}
 {CYAN}|   \   /   \ |  |  |/ ___/|  |  | /    ||    \  /    | /   \{RESET}
 {CYAN}|    \ |     ||  |  (   \_ |  |  ||  o  ||  o  )|  o  ||     |{RESET}
 {MAGENTA}|  D  ||  O  ||  |  |\__  ||  _  ||     ||     ||     ||  O  |{RESET}
 {MAGENTA}|     ||     ||  :  |/  \ ||  |  ||  _  ||  O  ||  _  ||     |{RESET}
 {MAGENTA}|     ||     ||     |\    ||  |  ||     ||     ||  |  ||     |{RESET}
 {MAGENTA}|_____| \___/  \__,_| \___||__|__||__|__||_____||__|__| \___/{RESET}"""

    lines = [
        "",
        logo,
        "",
        f"  {YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}",
        f"  {GREEN}App (single port){DIM}:{RESET}  http://localhost:{port}",
    ]
    if lan_ip and lan_ip != "127.0.0.1":
        lines.append(f"  {GREEN}LAN              {DIM}:{RESET}  http://{lan_ip}:{port}")
    lines += [
        f"  {GREEN}API docs         {DIM}:{RESET}  http://localhost:{port}/docs",
        f"  {GREEN}Frontend rebuild {DIM}:{RESET}  auto (vite build --watch)",
        f"  {YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}",
        "",
    ]
    return "\n".join(lines)


def _wait_for_dist(dist_dir: str, timeout: float = 60.0) -> bool:
    """Wait until dist/index.html exists (frontend build completed)."""
    deadline = time.monotonic() + timeout
    index_html = os.path.join(dist_dir, "index.html")
    while time.monotonic() < deadline:
        if os.path.isfile(index_html):
            return True
        time.sleep(0.5)
    return False


def main() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    web_dir = os.path.join(root, "apps", "web")
    api_dir = os.path.join(root, "apps", "api")
    dist_dir = os.path.join(web_dir, "dist")

    # ── Step 1: clean dist ────────────────────────────────────────
    print("Cleaning frontend dist...")
    if os.path.isdir(dist_dir):
        shutil.rmtree(dist_dir)

    # ── Step 2: vite build --watch in background ──────────────────
    # Vite 会监听前端源码变更并自动增量重构建。
    # --emptyOutDir 确保首次构建前 dist 为空。
    vite_proc = subprocess.Popen(
        ["pnpm", "exec", "vite", "build", "--watch", "--emptyOutDir"],
        cwd=web_dir,
    )

    def cleanup() -> None:
        if vite_proc.poll() is None:
            vite_proc.terminate()
            try:
                vite_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                vite_proc.kill()
                vite_proc.wait()

    # ── Step 3: wait for first build to complete ──────────────────
    print("Waiting for frontend initial build...")
    if not _wait_for_dist(dist_dir):
        print("ERROR: Frontend build did not complete in time.")
        cleanup()
        sys.exit(1)
    print("Frontend ready.")

    # ── Step 4: uvicorn in foreground (single port) ───────────────
    uvicorn_proc: subprocess.Popen[bytes] | None = None
    try:
        print(_serve_banner(BACKEND_PORT))

        uvicorn_proc = subprocess.Popen(
            [
                "uv", "run", "--directory", api_dir,
                "python", "-m", "uvicorn",
                "src.main:app",
                "--reload", "--reload-dir", api_dir,
                "--host", "0.0.0.0", "--port", str(BACKEND_PORT),
            ],
        )

        def sighandler(signum, frame):
            if uvicorn_proc and uvicorn_proc.poll() is None:
                uvicorn_proc.send_signal(signal.SIGTERM)

        signal.signal(signal.SIGTERM, sighandler)
        signal.signal(signal.SIGINT, sighandler)

        uvicorn_proc.wait()
    except KeyboardInterrupt:
        if uvicorn_proc is not None and uvicorn_proc.poll() is None:
            uvicorn_proc.terminate()
            uvicorn_proc.wait()
    finally:
        cleanup()


if __name__ == "__main__":
    main()
