"""Put scripts/lib on sys.path so stage scripts can `from paths import ...`."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPTS_DIR / "lib"

_lib = str(LIB_DIR)
if _lib not in sys.path:
    sys.path.insert(0, _lib)
