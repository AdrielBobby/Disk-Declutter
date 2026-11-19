"""Installed apps from the registry, with best-effort last-used time."""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from ..fsutil import dir_size
from ..models import APP, MEDIUM, Item

try:  # winreg only exists on Windows
    import winreg
except ImportError:  # pragma: no cover
    winreg = None

MIN_BYTES = 50 * 1024 * 1024   # skip tiny runtimes/redistributables
UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
HIVES = [
    ("HKLM", "HKEY_LOCAL_MACHINE", UNINSTALL_KEY, 0),
    ("HKLM", "HKEY_LOCAL_MACHINE", r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall", 0),
    ("HKCU", "HKEY_CURRENT_USER", UNINSTALL_KEY, 0),
]


def _read_values(key) -> dict:
    out = {}
    i = 0
    while True:
        try:
            name, value, _ = winreg.EnumValue(key, i)
        except OSError:
            return out
        out[name] = value
        i += 1


def _registry_entries(errors: list[str]) -> list[dict]:
    entries = []
    for _, hive_name, subkey, _ in HIVES:
        try:
            root = winreg.OpenKey(getattr(winreg, hive_name), subkey)
        except OSError:
            continue
        with root:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(root, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root, sub) as k:
                        entries.append(_read_values(k))
                except OSError as e:
                    errors.append(f"registry {sub}: {e}")
    return entries


def prefetch_map(prefetch_dir: str, errors: list[str]) -> dict[str, float]:
    """exe name (upper) -> newest .pf mtime. Needs admin; returns {} if unreadable."""
    result: dict[str, float] = {}
    try:
        with os.scandir(prefetch_dir) as it:
            for e in it:
                if not e.name.upper().endswith(".PF"):
                    continue
                exe = e.name.rsplit("-", 1)[0].upper()      # NAME.EXE-HASH.pf
                m = e.stat().st_mtime
                if m > result.get(exe, 0):
                    result[exe] = m
    except OSError:
        errors.append("Prefetch unreadable (run as administrator for better last-used accuracy)")
    return result


def _exes(location: str, max_depth: int = 2) -> list[str]:
    found = []
    base_depth = location.rstrip("\\/").count(os.sep)
    for dirpath, dirnames, filenames in os.walk(location):
        if dirpath.count(os.sep) - base_depth >= max_depth:
            dirnames[:] = []
        found += [os.path.join(dirpath, f) for f in filenames if f.lower().endswith(".exe")]
        if len(found) > 200:
            break
    return found


def last_used(location: str | None, install_date: str | None, prefetch: dict[str, float]) -> tuple[float | None, str]:
    """Best evidence of last use: Prefetch > newest exe atime/mtime > install date."""
    if location and os.path.isdir(location):
        exes = _exes(location)
        pf = [prefetch[os.path.basename(x).upper()] for x in exes if os.path.basename(x).upper() in prefetch]
        if pf:
            return max(pf), "prefetch"
        times = []
        for x in exes:
            try:
                st = os.stat(x)
                times.append(max(st.st_atime, st.st_mtime))
            except OSError:
                pass
        if times:
            return max(times), "exe_time"
    if install_date and len(install_date) == 8 and install_date.isdigit():
        try:
            return datetime.strptime(install_date, "%Y%m%d").timestamp(), "install_date"
        except ValueError:
            pass
    return None, "unknown"


EXE_PATH = re.compile(r'([A-Za-z]:\\[^"]*?\.exe)', re.I)


def guess_folder(v: dict) -> str | None:
    """Install folder from InstallLocation, else from the folder of the uninstaller/icon exe."""
    loc = (v.get("InstallLocation") or "").strip().strip('"')
    if loc:
        return loc
    for key in ("QuietUninstallString", "UninstallString", "DisplayIcon"):
        m = EXE_PATH.search(v.get(key) or "")
        if m:
            return os.path.dirname(m.group(1))
    return None


def entry_to_item(v: dict, prefetch: dict[str, float], errors: list[str]) -> Item | None:
    name = (v.get("DisplayName") or "").strip()
    if not name or v.get("SystemComponent") == 1 or v.get("ParentKeyName") or name.startswith("KS") and name[2:3].isdigit():
        return None
    if "update for" in name.lower() or "security update" in name.lower():
        return None

    location = guess_folder(v)
    if location and not os.path.isdir(location):
        return None   # ghost entry: the app's folder is gone but Windows still lists it

    size = int(v.get("EstimatedSize") or 0) * 1024
    if not size and location:
        size = dir_size(location, errors)
    if size < MIN_BYTES:
        return None

    ts, src = last_used(location, v.get("InstallDate"), prefetch)
    return Item(
        kind=APP, name=name, path=location or "", size_bytes=size,
        last_used=ts, last_used_source=src, risk=MEDIUM, deletable=False,
        uninstall_cmd=v.get("QuietUninstallString") or v.get("UninstallString"),
        extra={"publisher": v.get("Publisher"), "version": v.get("DisplayVersion"), "probe": location},
    )


def scan(stale_days: int, errors: list[str]) -> list[Item]:
    if winreg is None or sys.platform != "win32":
        errors.append("apps scanner only supports Windows")
        return []
    prefetch = prefetch_map(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "Prefetch"), errors)
    seen: set[str] = set()
    items: list[Item] = []
    for v in _registry_entries(errors):
        item = entry_to_item(v, prefetch, errors)
        if item and item.name.lower() not in seen:
            seen.add(item.name.lower())
            items.append(item)
    return sorted(items, key=lambda i: i.size_bytes, reverse=True)
