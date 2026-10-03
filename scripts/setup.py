"""
Doushabao full project setup.

Installs both:
  - Python backend dependencies via uv sync (in apps/api/)
  - JavaScript frontend dependencies via pnpm install (at project root)
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    api_dir = os.path.join(root, "apps", "api")

    print("=" * 50)
    print("Step 1/2: Installing Python backend dependencies...")
    print("=" * 50)
    result = subprocess.run(
        ["uv", "sync", "--directory", api_dir],
    )
    if result.returncode != 0:
        print("ERROR: uv sync failed", file=sys.stderr)
        sys.exit(result.returncode)

    print()
    print("=" * 50)
    print("Step 2/2: Installing frontend dependencies...")
    print("=" * 50)
    result = subprocess.run(
        ["pnpm", "install"],
        cwd=root,
    )
    if result.returncode != 0:
        print("ERROR: pnpm install failed", file=sys.stderr)
        sys.exit(result.returncode)

    print()
    print("All dependencies installed. Run `make dev` to start the dev server.")


if __name__ == "__main__":
    main()
