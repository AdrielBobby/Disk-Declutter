"""Installed apps from the registry, with best-effort last-used time."""

from __future__ import annotations

from ..models import Item


def scan(stale_days: int, errors: list[str]) -> list[Item]:
    """TODO: read Uninstall keys (HKLM/HKCU, WOW6432Node); last-used from Prefetch / Recent / exe atime."""
    return []
