"""Rule-based scoring: turn raw scanner items into reasons, confidence and risk."""

from __future__ import annotations

import os
import time

from .models import APP, CACHE, DUPLICATE, FILE, HIGH, LOW, MEDIUM, Item

# Extensions that are usually re-downloadable or disposable.
DISPOSABLE = {".exe", ".msi", ".iso", ".zip", ".rar", ".7z", ".tmp", ".bak", ".dmp", ".log", ".torrent"}
# Extensions that are usually personal / irreplaceable.
PERSONAL = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf", ".psd", ".kdbx", ".key",
            ".pem", ".jpg", ".jpeg", ".png", ".heic", ".raw", ".cr2", ".nef", ".mp4", ".mov", ".mkv"}


def _age_days(item: Item) -> int | None:
    if item.last_used is None:
        return None
    return max(0, int((time.time() - item.last_used) / 86400))


def _score_file(item: Item, stale_days: int) -> None:
    ext = os.path.splitext(item.name)[1].lower()
    age = _age_days(item)
    age_txt = f"untouched for {age} days" if age is not None else "no recent activity found"
    conf = 0.4
    risk = MEDIUM
    why = f"Large file, {age_txt}"

    if ext in DISPOSABLE:
        conf, risk = 0.75, LOW
        why += f" ({ext} files are usually re-downloadable)"
    elif ext in PERSONAL:
        conf, risk = 0.3, HIGH
        why += f" ({ext} may be personal data, review before clearing)"

    if age is not None and age > stale_days * 2:
        conf += 0.1
    if item.last_used_source == "mtime":
        conf -= 0.05   # modified-time only: weaker evidence it was never opened

    item.confidence, item.risk, item.reason = conf, risk, why


def _score_duplicate(item: Item) -> None:
    original = item.extra.get("original", "another location")
    item.confidence, item.risk = 0.85, LOW
    item.reason = f"Identical copy of {original} (content hash match)"


def _score_cache(item: Item) -> None:
    item.confidence, item.risk = 0.9, LOW
    item.reason = item.reason or "Cache/temp data that is rebuilt automatically"


def _score_app(item: Item, stale_days: int) -> None:
    item.deletable = False   # apps are uninstalled by the user, never deleted by us
    age = _age_days(item)
    if age is None:
        item.confidence, item.risk = 0.2, MEDIUM
        item.reason = "Could not determine when this app was last used"
    elif age > stale_days:
        item.confidence, item.risk = 0.6, MEDIUM
        item.reason = f"App not used for about {age} days"
    else:
        item.confidence, item.risk = 0.1, MEDIUM
        item.reason = f"Used recently ({age} days ago)"


def score_items(items: list[Item], stale_days: int) -> None:
    """Fill reason/confidence/risk in place."""
    for item in items:
        if item.kind == FILE:
            _score_file(item, stale_days)
        elif item.kind == DUPLICATE:
            _score_duplicate(item)
        elif item.kind == CACHE:
            _score_cache(item)
        elif item.kind == APP:
            _score_app(item, stale_days)
        item.confidence = round(min(1.0, max(0.0, item.confidence)), 2)
        if not item.deletable and item.kind != APP:
            item.reason += " [protected path, will not be offered for deletion]"
