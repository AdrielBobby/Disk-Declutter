"""One-command workflow: scan -> open report -> clean what the user selected."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

from . import config


def newest_selection(since: float) -> Path | None:
    """Newest selection.json (output folder or browser Downloads) written after `since`."""
    found = []
    for folder, pattern in ((config.OUTPUT_DIR, "selection*.json"), (config.HOME / "Downloads", "selection*.json")):
        for f in Path(folder).glob(pattern):
            try:
                if f.stat().st_mtime >= since:
                    found.append(f)
            except OSError:
                pass
    return max(found, key=lambda f: f.stat().st_mtime) if found else None


def run_go(args) -> int:
    from .clean import run_clean
    from .report import run_report
    from .scan import run_scan

    if run_scan(args):
        return 1
    started = time.time()
    if run_report(SimpleNamespace(open=True)):
        return 1

    print("\nIn the report: tick what to clear, then click 'Export selection.json'.")
    try:
        answer = input("Press Enter here once you've exported (or type q to quit without cleaning): ")
    except (EOFError, KeyboardInterrupt):
        return 0
    if answer.strip().lower().startswith("q"):
        print("Nothing was changed.")
        return 0

    sel = newest_selection(started)
    if sel is None:
        print("No new selection.json found. Export one from the report, then run: python -m declutter clean --apply")
        return 1
    print(f"Using {sel}")
    # apply=True with yes=False: lists exactly what will move, then asks for a final y/N.
    return run_clean(SimpleNamespace(selection=str(sel), apply=True, yes=False))
