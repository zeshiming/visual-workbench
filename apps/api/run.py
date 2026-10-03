"""
Top-level entry point for PyInstaller-frozen app and direct CLI usage.

This file lives at apps/api/ (not inside src/) so relative imports
in src/ work correctly when frozen by PyInstaller.
"""
from __future__ import annotations

import sys
import os

# Ensure the src package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import app  # noqa: E402, F401
from src.main import start  # noqa: E402


if __name__ == "__main__":
    start()
