"""Folder-size tree for the disk usage breakdown."""

from __future__ import annotations

import os

from .. import config
from ..fsutil import _is_link

MAX_DEPTH = 3     # levels kept in the output tree (deeper sizes still roll up)
TOP_N = 15        # biggest children kept per folder; the rest are merged into "other"


def _build(path: str, name: str, depth: int, errors: list[str]) -> dict:
    node = {"name": name, "path": path, "size": 0, "children": []}
    children: list[dict] = []
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if _is_link(entry):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        children.append(_build(entry.path, entry.name, depth + 1, errors))
                    elif entry.is_file(follow_symlinks=False):
                        node["size"] += entry.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
    except OSError as e:
        errors.append(f"{path}: {e}")

    # Own files + all descendant sizes.
    own_files = node["size"]
    node["size"] += sum(c["size"] for c in children)

    if depth < MAX_DEPTH:
        children.sort(key=lambda c: c["size"], reverse=True)
        kept, rest = children[:TOP_N], children[TOP_N:]
        other = own_files + sum(c["size"] for c in rest)
        if other > 0:
            kept.append({"name": "(other files)", "path": path, "size": other, "children": []})
        node["children"] = kept
    return node


def scan(errors: list[str], root: str | None = None) -> dict | None:
    """Return {name, path, size, children} for root (default: the user profile)."""
    root = root or str(config.HOME)
    if not os.path.isdir(root):
        return None
    return _build(root, os.path.basename(root) or root, 0, errors)
