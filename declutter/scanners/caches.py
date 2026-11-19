"""Caches and temp junk: %TEMP%, browser caches, npm/pip/gradle/nuget, stale node_modules, Recycle Bin."""

from __future__ import annotations

from ..models import Item


def scan(errors: list[str]) -> list[Item]:
    """TODO: measure known cache locations."""
    return []
