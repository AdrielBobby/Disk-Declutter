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
