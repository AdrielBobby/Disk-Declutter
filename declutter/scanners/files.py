"""Large / stale files and duplicates in user folders."""

from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict
from pathlib import Path

from .. import config
from ..models import DUPLICATE, FILE, Item

MIN_DUP_BYTES = 1 * 1024 * 1024   # ignore tiny files when looking for duplicates
CHUNK = 64 * 1024


def _walk(root: Path, errors: list[str]):
    """Yield (path, stat) for regular files under root. Skips symlinks/junctions, tolerates errors."""
    stack = [str(root)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            yield entry.path, entry.stat(follow_symlinks=False)
                    except OSError as e:
                        errors.append(f"{entry.path}: {e}")
        except OSError as e:
            errors.append(f"{current}: {e}")


def _last_used(st: os.stat_result) -> tuple[float, str]:
    """Best estimate of last use. Windows atime is unreliable, so the newer of atime/mtime wins."""
    if st.st_atime > st.st_mtime:
        return st.st_atime, "atime"
    return st.st_mtime, "mtime"


def _hash_file(path: str, partial: bool, size: int) -> str | None:
    h = hashlib.blake2b(digest_size=16)
    try:
        with open(path, "rb") as f:
            if partial:
                h.update(f.read(CHUNK))
                if size > CHUNK * 2:
                    f.seek(-CHUNK, os.SEEK_END)
                    h.update(f.read(CHUNK))
            else:
                while chunk := f.read(1024 * 1024):
                    h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _group(paths: list[str], key) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for p in paths:
        k = key(p)
        if k is not None:
            groups[k].append(p)
    return {k: v for k, v in groups.items() if len(v) > 1}


def find_duplicates(by_size: dict[int, list[str]]) -> list[list[str]]:
    """Group identical files: size -> partial hash -> full hash. Returns groups of 2+ paths."""
    result: list[list[str]] = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for part_group in _group(paths, lambda p: _hash_file(p, True, size)).values():
            for full_group in _group(part_group, lambda p: _hash_file(p, False, size)).values():
                result.append(full_group)
    return result


def scan(dirs, min_size_mb: int, stale_days: int, errors: list[str]) -> list[Item]:
    roots = [Path(d) for d in dirs] if dirs else config.DEFAULT_SCAN_DIRS
    min_bytes = min_size_mb * 1024 * 1024
    stale_cutoff = time.time() - stale_days * 86400

    items: dict[str, Item] = {}
    by_size: dict[int, list[str]] = defaultdict(list)
    meta: dict[str, os.stat_result] = {}
    seen: set[str] = set()

    for root in roots:
        if not root.exists():
            continue
        for path, st in _walk(root, errors):
            norm = os.path.normcase(path)
            if norm in seen:          # overlapping scan roots
                continue
            seen.add(norm)
            if st.st_size >= MIN_DUP_BYTES:
                by_size[st.st_size].append(path)
                meta[path] = st
            if st.st_size >= min_bytes:
                last, src = _last_used(st)
                if last < stale_cutoff:
                    items[path] = Item(
                        kind=FILE,
                        name=os.path.basename(path),
                        path=path,
                        size_bytes=st.st_size,
                        last_used=last,
                        last_used_source=src,
                        deletable=not config.is_protected(path),
                    )

    for group in find_duplicates(by_size):
        # Keep the oldest copy as the "original"; flag the rest.
        group.sort(key=lambda p: (meta[p].st_mtime, len(p)))
        original = group[0]
        for dup in group[1:]:
            st = meta[dup]
            last, src = _last_used(st)
            items[dup] = Item(
                kind=DUPLICATE,
                name=os.path.basename(dup),
                path=dup,
                size_bytes=st.st_size,
                last_used=last,
                last_used_source=src,
                deletable=not config.is_protected(dup),
                extra={"original": original, "copies": len(group)},
            )

    return sorted(items.values(), key=lambda i: i.size_bytes, reverse=True)
