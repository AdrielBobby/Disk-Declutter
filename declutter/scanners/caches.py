"""Caches and temp junk: %TEMP%, browser caches, package manager caches, stale node_modules."""

from __future__ import annotations

import os
import time
from pathlib import Path

from .. import config
from ..fsutil import _is_link, dir_size, newest_mtime
from ..models import CACHE, LOW, Item

MIN_BYTES = 20 * 1024 * 1024   # ignore locations smaller than this


def _known_locations() -> list[tuple[str, Path, str]]:
    """(label, path, why) for caches that are rebuilt automatically."""
    local = Path(os.environ.get("LOCALAPPDATA", config.HOME / "AppData" / "Local"))
    roaming = Path(os.environ.get("APPDATA", config.HOME / "AppData" / "Roaming"))
    win = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    rebuilt = "Rebuilt automatically when needed"
    return [
        ("User temp files", Path(os.environ.get("TEMP", local / "Temp")), "Temporary files; safe once apps are closed"),
        ("Windows temp", win / "Temp", "Temporary files (may need admin to clear)"),
        ("Chrome cache", local / "Google" / "Chrome" / "User Data" / "Default" / "Cache", rebuilt),
        ("Chrome code cache", local / "Google" / "Chrome" / "User Data" / "Default" / "Code Cache", rebuilt),
        ("Edge cache", local / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache", rebuilt),
        ("Edge code cache", local / "Microsoft" / "Edge" / "User Data" / "Default" / "Code Cache", rebuilt),
        ("Brave cache", local / "BraveSoftware" / "Brave-Browser" / "User Data" / "Default" / "Cache", rebuilt),
        ("npm cache", local / "npm-cache", "Re-downloaded on next install"),
        ("pip cache", local / "pip" / "Cache", "Re-downloaded on next install"),
        ("Yarn cache", local / "Yarn" / "Cache", "Re-downloaded on next install"),
        ("pnpm store", local / "pnpm" / "store", "Re-downloaded on next install"),
        ("Gradle cache", config.HOME / ".gradle" / "caches", "Re-downloaded on next build"),
        ("NuGet packages cache", config.HOME / ".nuget" / "packages", "Restored on next build"),
        ("Cargo registry cache", config.HOME / ".cargo" / "registry" / "cache", "Re-downloaded on next build"),
        ("Windows Update download cache", win / "SoftwareDistribution" / "Download", "Re-downloaded if needed (needs admin)"),
        ("Crash dumps", local / "CrashDumps", "Only useful for debugging old crashes"),
        ("Discord cache", roaming / "discord" / "Cache", rebuilt),
        ("Spotify cache", local / "Spotify" / "Data", rebuilt),
        ("VS Code cache", roaming / "Code" / "Cache", rebuilt),
        ("VS Code cached data", roaming / "Code" / "CachedData", rebuilt),
    ]


def _find_node_modules(roots: list[Path], max_depth: int = 5):
    """Yield node_modules dirs under roots without descending into them."""
    skip = {"appdata", "$recycle.bin", ".git", ".venv", "venv"}
    stack = [(str(r), 0) for r in roots if r.is_dir()]
    while stack:
        current, depth = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if _is_link(entry) or not entry.is_dir(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    if entry.name == "node_modules":
                        yield entry.path
                    elif depth < max_depth and entry.name.lower() not in skip:
                        stack.append((entry.path, depth + 1))
        except OSError:
            continue


def scan(errors: list[str], stale_days: int = 90) -> list[Item]:
    items: list[Item] = []

    for label, path, why in _known_locations():
        if not path.is_dir():
            continue
        size = dir_size(str(path), errors)
        if size < MIN_BYTES:
            continue
        items.append(Item(
            kind=CACHE, name=label, path=str(path), size_bytes=size,
            last_used=newest_mtime(str(path)), last_used_source="mtime",
            reason=why, risk=LOW, deletable=not config.is_protected(path),
            extra={"category": "cache"},
        ))

    # node_modules in project folders not touched for a while (npm install brings them back).
    cutoff = time.time() - stale_days * 86400
    roots = [p for p in config.HOME.iterdir() if p.is_dir() and p.name.lower() != "appdata"] if config.HOME.is_dir() else []
    for nm in _find_node_modules(roots):
        project = os.path.dirname(nm)
        last = max(newest_mtime(nm), newest_mtime(project))
        if last >= cutoff:
            continue
        size = dir_size(nm, errors)
        if size < MIN_BYTES:
            continue
        items.append(Item(
            kind=CACHE, name=f"node_modules ({os.path.basename(project)})", path=nm, size_bytes=size,
            last_used=last, last_used_source="mtime",
            reason="Dependencies of a project untouched for a while; `npm install` restores them",
            risk=LOW, deletable=not config.is_protected(nm), extra={"category": "node_modules"},
        ))

    return sorted(items, key=lambda i: i.size_bytes, reverse=True)
