#!/usr/bin/env python3
"""Skill-local command launcher for TokenEconomizer configuration."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tokeneconomizer.plugin import cli

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "--host", "antigravity", *sys.argv[1:]]
    raise SystemExit(cli.main())
