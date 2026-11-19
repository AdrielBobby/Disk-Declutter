"""Large / stale files and duplicates in user folders."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import defaultdict
from pathlib import Path

from .. import config
from ..fsutil import is_link
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
                        if is_link(entry):   # symlinks and junctions (e.g. legacy "My Videos")
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


class HashCache:
    """Remembers hashes between runs, keyed by path + size + mtime, so unchanged files are not re-read."""

    def __init__(self, path: Path | None = None):
        self.path = path
        self.data: dict[str, str] = {}
        if path and path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self.data = {}

    def hash(self, p: str, partial: bool, size: int) -> str | None:
        try:
            key = f"{os.path.normcase(p)}|{size}|{os.stat(p).st_mtime_ns}|{int(partial)}"
        except OSError:
            return None
        if key not in self.data:
            digest = _hash_file(p, partial, size)
            if digest is None:
                return None
            self.data[key] = digest
        return self.data[key]

    def save(self, live_paths: set[str]) -> None:
        """Persist, dropping entries for files that no longer exist in the scan."""
        if not self.path:
            return
        keep = {k: v for k, v in self.data.items() if k.split("|", 1)[0] in live_paths}
        try:
            self.path.parent.mkdir(exist_ok=True)
            self.path.write_text(json.dumps(keep), encoding="utf-8")
        except OSError:
            pass


def find_duplicates(by_size: dict[int, list[str]], cache: HashCache | None = None) -> list[list[str]]:
    """Group identical files: size -> partial hash -> full hash. Returns groups of 2+ paths."""
    cache = cache or HashCache()
    result: list[list[str]] = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for part_group in _group(paths, lambda p: cache.hash(p, True, size)).values():
            for full_group in _group(part_group, lambda p: cache.hash(p, False, size)).values():
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

    cache = HashCache(config.HASH_CACHE)
    for group in find_duplicates(by_size, cache):
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

    cache.save({os.path.normcase(p) for p in meta})
    return sorted(items.values(), key=lambda i: i.size_bytes, reverse=True)
