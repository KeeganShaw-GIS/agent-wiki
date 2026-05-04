#!/usr/bin/env python3
"""Shim — kept for backward compatibility with existing git hooks.

Prefer using the `agent-wiki` CLI after installing the package:
  pip install -e /path/to/chatbox-wiki
"""
import sys
from pathlib import Path

# Allow running as a plain script without the package installed
sys.path.insert(0, str(Path(__file__).parent.parent))

from wiki.cli import main

if __name__ == "__main__":
    main()
