#!/usr/bin/env python3
"""Install the dev team into any project, for one or more agent platforms.

Interactive by default in a terminal; scriptable with flags. Cross-platform
(Windows, Linux, macOS), Python 3 stdlib only. See installer/cli.py for usage.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from installer.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
