"""
Generate platform-specific icons for the desktop app from the project logo.

Usage:
  python scripts/generate-icons.py

Requires Pillow: pip install Pillow
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
from io import BytesIO

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(ROOT, "electron", "assets")
LOGO_PATH = os.path.join(ROOT, "apps", "web", "src", "assets", "images", "logo.png")
ICON_PATH = os.path.join(ASSETS_DIR, "icon.png")


def _check_deps() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def _install_deps():
    print("  安装 Pillow…")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "Pillow"],
        check=True,
    )


def _ensure_icon_png():
    """Copy logo.png → electron/assets/icon.png if not already there."""
    if os.path.isfile(ICON_PATH) and os.path.getsize(ICON_PATH) > 0:
        return
    if not os.path.isfile(LOGO_PATH):
        print(f"  ✗ Logo not found: {LOGO_PATH}")
        sys.exit(1)
    os.makedirs(ASSETS_DIR, exist_ok=True)
    img = Image.open(LOGO_PATH)
    img.save(ICON_PATH, format="PNG")
    print(f"  ✓ {ICON_PATH} ({img.width}x{img.height})")


def _png_to_ico(png_path: str, ico_path: str, sizes=(256, 128, 64, 48, 32, 16)):
    img = Image.open(png_path)
    # Downsize to 256 for ICO master
    master = img.resize((256, 256), Image.LANCZOS) if img.width > 256 else img
    icons = [master.resize((s, s), Image.LANCZOS) for s in sizes if s <= master.width]
    if not icons:
        icons = [master]
    icons[0].save(
        ico_path,
        format="ICO",
        sizes=[(i.width, i.height) for i in icons],
        append_images=icons[1:],
    )
    print(f"  ✓ {ico_path}")


def _png_to_icns(png_path: str, icns_path: str):
    img = Image.open(png_path)
    sizes = {
        "ic07": 128,
        "ic08": 256,
        "ic09": 512,
    }
    master = img.resize((512, 512), Image.LANCZOS) if img.width != 512 else img
    with open(icns_path, "wb") as f:
        f.write(b"icns")
        icon_data = b""
        for ostype, size in sizes.items():
            resized = master.resize((size, size), Image.LANCZOS)
            buf = BytesIO()
            resized.save(buf, format="PNG")
            png_data = buf.getvalue()
            entry = ostype.encode("ascii") + struct.pack(">I", len(png_data) + 8) + png_data
            icon_data += entry
        f.write(struct.pack(">I", len(icon_data) + 8))
        f.write(icon_data)
    print(f"  ✓ {icns_path}")


def main():
    print()
    print("  ╔══════════════════════════════════════════════════╗")
    print("  ║         Doushabao Icon Generator                ║")
    print("  ╚══════════════════════════════════════════════════╝")
    print()

    if not _check_deps():
        _install_deps()

    _ensure_icon_png()

    # macOS .icns (electron-builder can also convert PNG→ICNS automatically)
    icns_path = os.path.join(ASSETS_DIR, "icon.icns")
    _png_to_icns(ICON_PATH, icns_path)

    # Windows .ico
    ico_path = os.path.join(ASSETS_DIR, "icon.ico")
    _png_to_ico(ICON_PATH, ico_path)

    print()
    print("  ✨ 图标生成完成！electron-builder 可直接使用 icon.png")
    print()


if __name__ == "__main__":
    main()
