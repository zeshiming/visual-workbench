"""
桌面应用构建脚本。

构建流程：
  1. 安装 electron 依赖（pnpm install in electron/）
  2. 构建前端（vite build）
  3. 用 PyInstaller 打包 Python 后端 → 独立可执行文件
  4. 复制产物到 electron-builder 的资源目录
  5. 运行 electron-builder 生成平台安装包

用法：
  python scripts/build-desktop.py                    # 构建当前平台
  python scripts/build-desktop.py --mac              # 仅 macOS
  python scripts/build-desktop.py --win              # 仅 Windows
  python scripts/build-desktop.py --linux            # 仅 Linux
  python scripts/build-desktop.py --all              # 所有平台
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_DIR = os.path.join(ROOT, "apps", "web")
API_DIR = os.path.join(ROOT, "apps", "api")
ELECTRON_DIR = os.path.join(ROOT, "electron")
DIST_DESKTOP = os.path.join(ROOT, "dist-desktop")
STAGING_DIR = os.path.join(ELECTRON_DIR, "build-staging")

SYSTEM = platform.system().lower()  # "darwin", "linux", "windows"
MACHINE = platform.machine().lower()


def banner():
    print()
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║       Doushabao Desktop Build Tool              ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print()


def run(cmd, cwd=None, desc=None):
    """Run a shell command, print output live, exit on failure."""
    if desc:
        print(f"\n  → {desc}")
        print(f"    $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd or ROOT)
    if result.returncode != 0:
        print(f"\n  ✗ 命令失败 (exit={result.returncode})")
        sys.exit(result.returncode)
    return result


# ── Step 0: Validate prerequisites ──────────────────────────────


def validate_prereqs():
    """Check required tools exist."""
    missing = []
    for tool in ["node", "pnpm", "uv", "python"]:
        if not shutil.which(tool):
            missing.append(tool)
    if missing:
        print(f"  缺少必要工具: {', '.join(missing)}")
        print("  请先安装: pnpm (npm install -g pnpm), uv, Python 3.11+")
        sys.exit(1)
    print(f"  ✓ System: {SYSTEM}/{MACHINE}, Node={_version('node')}, Python={_version('python')}")


def _version(tool):
    try:
        return subprocess.check_output([tool, "--version"], text=True).strip()
    except Exception:
        return "?"


# ── Step 1: Install electron dependencies ───────────────────────


def install_electron_deps():
    """Install all workspace dependencies (electron is in workspace now)."""
    run(["pnpm", "install"], cwd=ROOT, desc="安装依赖")
    # 强制下载 Electron 二进制（pnpm v10 默认屏蔽构建脚本，仅设 config 对已有 lockfile 无效）
    run(["pnpm", "rebuild", "electron"], cwd=ROOT, desc="下载 Electron")


# ── Step 2: Build Vue frontend ──────────────────────────────────


def build_frontend():
    run(
        ["pnpm", "build"],
        cwd=WEB_DIR,
        desc="构建前端 (Vite)",
    )
    dist = os.path.join(WEB_DIR, "dist")
    if not os.path.isdir(dist):
        print(f"  ✗ 前端构建失败: {dist} 不存在")
        sys.exit(1)
    print(f"  ✓ 前端构建完成: {dist}")


# ── Step 3: Bundle Python backend with PyInstaller ──────────────


def build_backend():
    """Use PyInstaller to create a standalone backend executable."""
    print("\n  → 打包 Python 后端 (PyInstaller)")

    # Ensure PyInstaller is available (use --with to inject without modifying project deps)
    pyinstaller_check = subprocess.run(
        ["uv", "run", "--with", "pyinstaller", "--directory", API_DIR, "pyinstaller", "--version"],
        capture_output=True, text=True, cwd=API_DIR,
    )
    if pyinstaller_check.returncode != 0:
        print("  安装 PyInstaller…")
        run(
            ["uv", "add", "--directory", API_DIR, "--dev", "pyinstaller"],
            desc="安装 PyInstaller",
        )

    # Clean previous build
    for d in ["build", "dist"]:
        p = os.path.join(API_DIR, d)
        if os.path.isdir(p):
            shutil.rmtree(p)

    # ── Build spec arguments ──
    frontend_dist = os.path.join(WEB_DIR, "dist")

    datas_args = []
    if os.path.isdir(frontend_dist):
        datas_args = ["--add-data", f"{frontend_dist}:frontend"]

    pyi_args = (
        ["--clean", "--noconfirm"]
        + ["--onedir"]
        + ["--name", "doushabao-api"]
        + ["--collect-data", "litellm"]
        + ["--distpath", "dist"]
        + ["--workpath", "build/pyinstaller"]
        + ["--specpath", "build"]
        + datas_args
        + ["run.py"]
    )

    # uv run --with pyinstaller makes pyinstaller available in project env
    cmd = ["uv", "run", "--with", "pyinstaller", "--directory", API_DIR, "pyinstaller"] + pyi_args

    start = time.monotonic()
    result = subprocess.run(cmd, cwd=API_DIR)
    elapsed = time.monotonic() - start

    if result.returncode != 0:
        print(f"\n  ✗ 后端打包失败 (exit={result.returncode})")
        sys.exit(result.returncode)

    # Verify binary exists
    binary_dir = os.path.join(API_DIR, "dist", "doushabao-api")
    if not os.path.isdir(binary_dir):
        print(f"  ✗ 后端构建产物不存在: {binary_dir}")
        sys.exit(1)

    print(f"  ✓ 后端打包完成 ({elapsed:.0f}s): {binary_dir}")

    # Move the frontend from inside the PyInstaller dir to alongside it
    # (Electron needs to know the path independently)
    return binary_dir


# ── Step 4: Stage resources for electron-builder ────────────────


def stage_resources(backend_dir):
    """Copy backend binary + frontend to electron/build-staging/."""
    if os.path.isdir(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)

    # ── Backend binary ──
    backend_staging = os.path.join(STAGING_DIR, "backend")
    shutil.copytree(backend_dir, backend_staging)
    print(f"  ✓ 后端已暂存: {backend_staging}")

    # ── Frontend dist ──
    frontend_src = os.path.join(WEB_DIR, "dist")
    frontend_staging = os.path.join(STAGING_DIR, "frontend")
    if os.path.isdir(frontend_src):
        shutil.copytree(frontend_src, frontend_staging)
        print(f"  ✓ 前端已暂存: {frontend_staging}")
    else:
        print("  ⚠ 前端构建产物不存在，跳过")

    print(f"  ✓ 构建资源已就绪: {STAGING_DIR}")


# ── Step 5: Run electron-builder ────────────────────────────────


def run_electron_builder(targets):
    """Run electron-builder with specified platform targets."""
    print(f"\n  → 打包桌面应用 (electron-builder, targets={targets or 'current'})")

    # electron is in workspace; use direct binary path for reliability
    electron_builder = os.path.join(ROOT, "node_modules", ".bin", "electron-builder")
    if not os.path.isfile(electron_builder):
        electron_builder = os.path.join(ELECTRON_DIR, "node_modules", ".bin", "electron-builder")
    dist_cmd = [electron_builder]

    # Run from electron/ so it reads electron/package.json as app package (not root's)
    builder_cwd = ELECTRON_DIR
    if targets:
        for t in targets:
            dist_cmd.append(f"--{t}")
    else:
        if SYSTEM == "darwin":
            dist_cmd.append("--mac")
        elif SYSTEM == "windows":
            dist_cmd.append("--win")
        else:
            dist_cmd.append("--linux")

    # Set electron-builder config env vars for staging resources
    env = os.environ.copy()
    env["DOUSHABAO_STAGING_DIR"] = STAGING_DIR
    env["ELECTRON_BUILDER_ALLOW_UNRESOLVED_DATASETS"] = "true"

    start = time.monotonic()
    result = subprocess.run(dist_cmd, cwd=builder_cwd, env=env)
    elapsed = time.monotonic() - start

    if result.returncode != 0:
        print(f"\n  ✗ 桌面打包失败 (exit={result.returncode})")
        sys.exit(result.returncode)

    print(f"\n  ✓ 桌面应用打包完成 ({elapsed:.0f}s)")
    print(f"    输出目录: {DIST_DESKTOP}")

    # List output files
    if os.path.isdir(DIST_DESKTOP):
        print()
        for f in sorted(os.listdir(DIST_DESKTOP)):
            fpath = os.path.join(DIST_DESKTOP, f)
            size = os.path.getsize(fpath)
            if size > 1024 * 1024:
                size_str = f"{size / 1024 / 1024:.1f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} B"
            print(f"    📦 {f:40s} {size_str}")


# ═════════════════════════════════════════════════════════════════
#  Main
# ═════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="构建 Doushabao 桌面应用")
    parser.add_argument("--mac", action="store_true", help="构建 macOS (DMG)")
    parser.add_argument("--win", action="store_true", help="构建 Windows (NSIS)")
    parser.add_argument("--linux", action="store_true", help="构建 Linux (AppImage/deb)")
    parser.add_argument("--all", action="store_true", help="构建所有平台")
    parser.add_argument("--skip-frontend", action="store_true", help="跳过前端构建")
    parser.add_argument("--skip-backend", action="store_true", help="跳过后端打包")
    parser.add_argument("--skip-electron", action="store_true", help="跳过 Electron 打包（仅构建后端二进制）")
    args = parser.parse_args()

    banner()
    validate_prereqs()

    # Determine targets
    targets = []
    if args.all:
        targets = ["mac", "win", "linux"]
    else:
        for t in ["mac", "win", "linux"]:
            if getattr(args, t):
                targets.append(t)

    # ── Step 1: Electron deps ──
    if not args.skip_electron:
        install_electron_deps()

    # ── Step 2: Frontend ──
    if not args.skip_frontend:
        build_frontend()

    # ── Step 3: Backend binary ──
    backend_dir = None
    if not args.skip_backend:
        backend_dir = build_backend()

    # ── Step 4: Stage resources ──
    if backend_dir and not args.skip_electron:
        stage_resources(backend_dir)

    # ── Step 5: electron-builder ──
    if args.skip_electron:
        print()
        print("  ✓ 后端二进制构建完成（--skip-electron 跳过桌面打包）")
        print(f"    产物: {os.path.join(API_DIR, 'dist', 'doushabao-api')}")
        print()
        return

    run_electron_builder(targets)

    print()
    print("  ✨ 桌面应用构建完成！")
    print()


if __name__ == "__main__":
    main()
