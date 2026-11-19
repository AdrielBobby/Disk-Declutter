"""Defaults and safety rules."""

from __future__ import annotations

import os
from pathlib import Path

HOME = Path(os.environ.get("USERPROFILE", Path.home()))

# Folders scanned for large / stale files.
DEFAULT_SCAN_DIRS = [HOME / n for n in ("Downloads", "Documents", "Desktop", "Videos", "Pictures", "Music")]

# Thresholds (overridable from the CLI).
MIN_SIZE_MB = 100          # only report files at least this big
STALE_DAYS = 180           # not touched for this long counts as stale

# Paths the tool must never offer for deletion. Matched as prefixes (case-insensitive).
_WIN = Path(os.environ.get("SystemRoot", r"C:\Windows"))
_PF = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
_PF86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
_PD = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
_APPDATA = Path(os.environ.get("APPDATA", HOME / "AppData" / "Roaming"))

PROTECTED_PATHS = [
    _WIN,
    _PF,
    _PF86,
    _PD,
    Path(_WIN.anchor) / "Users" / "Default",
    Path(_WIN.anchor) / "System Volume Information",
]
# Exact folders that must not be removed themselves (their contents may still be listed).
PROTECTED_EXACT = [HOME, *DEFAULT_SCAN_DIRS, _APPDATA, HOME / "AppData", HOME / "AppData" / "Local"]

OUTPUT_DIR = Path("output")
REPORT_FILE = OUTPUT_DIR / "report.html"
SCAN_FILE = OUTPUT_DIR / "scan.json"
SELECTION_FILE = OUTPUT_DIR / "selection.json"
CLEANUP_LOG = OUTPUT_DIR / "cleanup_log.json"

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1"   # override with --model


def _norm(p: Path | str) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def is_protected(path: Path | str) -> bool:
    """True if the path is inside, or equal to, a protected location."""
    n = _norm(path)
    for exact in PROTECTED_EXACT:
        if n == _norm(exact):
            return True
    for base in PROTECTED_PATHS:
        b = _norm(base)
        if n == b or n.startswith(b + os.sep):
            return True
    return False
