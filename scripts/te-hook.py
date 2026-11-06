#!/usr/bin/env python3
"""Antigravity hook launcher. The event name is supplied by hooks.json."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["TE_PLUGIN_ROOT"] = str(ROOT)
if len(sys.argv) > 1:
    os.environ["TE_HOOK_EVENT"] = sys.argv[1]

from tokeneconomizer.plugin import hook

if __name__ == "__main__":
    raise SystemExit(hook.main(["--host", "antigravity"]))
