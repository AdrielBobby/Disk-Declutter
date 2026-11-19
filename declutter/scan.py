"""Orchestrates the scanners and writes output/scan.json."""

from __future__ import annotations

import json
import time

from . import config
from .models import ScanResult
from .scanners import apps, caches, files, usage
from .scoring import score_items


def _stage(label: str, fn):
    """Run one scanner, printing what it is doing and how long it took."""
    print(f"{label}...", end=" ", flush=True)
    start = time.time()
    out = fn()
    print(f"{time.time() - start:.1f}s")
    return out


def run_scan(args) -> int:
    result = ScanResult(scanned_at=time.time())
    skip = set(args.skip)
    began = time.time()

    if "files" not in skip:
        result.items += _stage("Scanning files and looking for duplicates", lambda: files.scan(
            args.dirs, args.min_size_mb, args.stale_days, result.errors))
    if "apps" not in skip:
        result.items += _stage("Scanning installed apps", lambda: apps.scan(args.stale_days, result.errors))
    if "caches" not in skip:
        result.items += _stage("Scanning caches and temp files", lambda: caches.scan(result.errors))
    if "usage" not in skip:
        result.usage_tree = _stage("Building disk usage breakdown", lambda: usage.scan(result.errors))

    score_items(result.items, args.stale_days)

    if args.ai:
        from . import ai
        _stage(f"Asking {args.model} about borderline items", lambda: ai.review(result.items, model=args.model))

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    config.SCAN_FILE.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

    reclaimable = sum(i.size_bytes for i in result.items if i.deletable)
    apps_size = sum(i.size_bytes for i in result.items if not i.deletable and i.kind == "app")
    print(f"\nDone in {time.time() - began:.0f}s: {len(result.items)} candidates, "
          f"{reclaimable / 1e9:.2f} GB clearable, {apps_size / 1e9:.1f} GB in installed apps (uninstall manually).")
    if result.errors:
        print(f"{len(result.errors)} location(s) could not be read (permissions); see 'errors' in {config.SCAN_FILE}.")
    print("Next: python -m declutter report --open")
    return 0
