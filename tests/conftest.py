# tests/conftest.py
"""Đảm bảo import 'src.xxx' hoạt động khi chạy pytest từ bất kỳ đâu."""
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
