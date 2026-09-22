#!/usr/bin/env python3
"""Install the parent-repository Neon layer; keep the Kickstart submodule intact."""
import runpy
from pathlib import Path
import sys

if sys.version_info < (3, 10):
    raise SystemExit("Neon requires Python 3.10 or newer.")
runpy.run_path(str(Path(__file__).resolve().parent / "neon" / "install.py"), run_name="__main__")
