"""Small filesystem helpers shared by scanners."""

from __future__ import annotations

import os


def is_link(entry: os.DirEntry) -> bool:
    try:
        return entry.is_symlink() or entry.is_junction()
    except OSError:
        return True


def dir_size(path: str, errors: list[str] | None = None) -> int:
    """Total size in bytes of regular files under path. Skips symlinks and junctions."""
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if is_link(entry):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
        except OSError as e:
            if errors is not None:
                errors.append(f"{current}: {e}")
    return total


def newest_mtime(path: str) -> float:
    """mtime of the directory itself (cheap proxy for 'last touched')."""
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0.0


def real_path(path: str | os.PathLike) -> str:
    r"""Resolve Microsoft Store Python's AppData virtualization.

    Store-installed Python redirects writes under %LOCALAPPDATA%/%APPDATA% into
    %LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.*\LocalCache\{Local,Roaming}. Python sees
    the redirected files at the normal path, but File Explorer and every other program do not. If a
    virtualized copy exists, return where it really lives so reports and cleanup point at real files.
    """
    p = os.path.abspath(str(path))
    local = os.environ.get("LOCALAPPDATA")
    roaming = os.environ.get("APPDATA")
    if not local:
        return p
    packages = os.path.join(local, "Packages")
    try:
        pkgs = [d for d in os.listdir(packages) if d.startswith("PythonSoftwareFoundation.Python.")]
    except OSError:
        return p
    for base, sub in ((local, "Local"), (roaming, "Roaming")):
        if not base:
            continue
        rel = os.path.relpath(p, base) if os.path.normcase(p).startswith(os.path.normcase(base) + os.sep) else None
        if rel is None:
            continue
        for pkg in pkgs:
            candidate = os.path.join(packages, pkg, "LocalCache", sub, rel)
            if os.path.exists(candidate):
                return candidate
    return p
