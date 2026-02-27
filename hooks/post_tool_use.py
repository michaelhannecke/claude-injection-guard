#!/usr/bin/env python3
"""
Claude Code PostToolUse hook entry point.

Thin wrapper that ensures the guard package is importable
(adds project root to sys.path) and delegates to the real
implementation in guard.post_tool_use.
"""

import sys
from pathlib import Path

# Add project root so `guard` package is importable even without pip install
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guard.post_tool_use import main  # noqa: E402

if __name__ == "__main__":
    main()
