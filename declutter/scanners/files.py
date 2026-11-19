"""Large / stale files and duplicates in user folders."""

from __future__ import annotations

from ..models import Item


def scan(dirs, min_size_mb: int, stale_days: int, errors: list[str]) -> list[Item]:
    """TODO: os.scandir walk; size, mtime, atime; duplicates via size -> partial hash -> full hash."""
    return []
