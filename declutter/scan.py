"""Orchestrates the scanners and writes output/scan.json."""

from __future__ import annotations

import json
import time

from . import config
from .models import ScanResult
from .scanners import apps, caches, files, usage
from .scoring import score_items


def run_scan(args) -> int:
    result = ScanResult(scanned_at=time.time())
    skip = set(args.skip)

    if "files" not in skip:
        print("Scanning files...")
        result.items += files.scan(args.dirs, args.min_size_mb, args.stale_days, result.errors)
    if "apps" not in skip:
        print("Scanning installed apps...")
        result.items += apps.scan(args.stale_days, result.errors)
    if "caches" not in skip:
        print("Scanning caches and temp files...")
        result.items += caches.scan(result.errors)
    if "usage" not in skip:
        print("Building disk usage breakdown...")
        result.usage_tree = usage.scan(result.errors)

    score_items(result.items, args.stale_days)

    if args.ai:
        from . import ai
        print("Asking local model about borderline items...")
        ai.review(result.items, model=args.model)

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    config.SCAN_FILE.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    total = sum(i.size_bytes for i in result.items if i.deletable)
    print(f"Done: {len(result.items)} candidates, ~{total / 1e9:.2f} GB reclaimable -> {config.SCAN_FILE}")
    return 0
