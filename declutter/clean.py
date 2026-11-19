"""Send user-selected items to the Recycle Bin. Dry run unless --apply is passed.

Safety rules (all enforced here, not just in the report):
  * Only paths present in the last scan.json and flagged deletable can be cleaned,
    so a hand-edited selection.json cannot name arbitrary files.
  * Protected locations are refused again at clean time.
  * Apps are never removed; duplicates need their kept original to still exist.
  * Nothing is permanently deleted: items go to the Recycle Bin, and anything the
    Bin cannot hold (Windows would delete it for real) is refused.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from . import config
from .fsutil import dir_size

try:
    import winreg
except ImportError:  # pragma: no cover
    winreg = None

BIN_VOLUMES = r"Software\Microsoft\Windows\CurrentVersion\Explorer\BitBucket\Volume"


# ---------------------------------------------------------------- Recycle Bin limits
def recycle_bin_limit(path: str) -> tuple[int | None, bool]:
    """(max item size in bytes, nuke_on_delete). Conservative: smallest configured volume cap,
    else 10% of the drive. nuke_on_delete means the Bin is bypassed (deletes are permanent)."""
    caps: list[int] = []
    nuke = False
    if winreg is not None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, BIN_VOLUMES) as root:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(root, i)
                    except OSError:
                        break
                    i += 1
                    with winreg.OpenKey(root, sub) as k:
                        try:
                            if winreg.QueryValueEx(k, "NukeOnDelete")[0]:
                                nuke = True
                        except OSError:
                            pass
                        try:
                            caps.append(int(winreg.QueryValueEx(k, "MaxCapacity")[0]) * 1024 * 1024)
                        except OSError:
                            pass
        except OSError:
            pass
    if caps:
        return min(caps), nuke
    try:
        return int(shutil.disk_usage(os.path.splitdrive(os.path.abspath(path))[0] + "\\").total * 0.10), nuke
    except OSError:
        return None, nuke


# ---------------------------------------------------------------- loading + validation
def load_selection(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["items"] if isinstance(data, dict) else data


def _is_link(p: str) -> bool:
    return os.path.islink(p) or (hasattr(os.path, "isjunction") and os.path.isjunction(p))


def validate(entries: list[dict], scan_items: dict[str, dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Split selection into (accepted scan items, refused (entry, reason))."""
    accepted: list[dict] = []
    refused: list[tuple[dict, str]] = []
    seen: set[str] = set()
    for e in entries:
        p = os.path.normcase(os.path.abspath(str(e.get("path", ""))))
        item = scan_items.get(p)
        if p in seen:
            continue
        seen.add(p)
        if item is None:
            refused.append((e, "not found in the last scan (re-run scan)"))
        elif item["kind"] == "app":
            refused.append((e, "apps must be uninstalled by you"))
        elif not item.get("deletable"):
            refused.append((e, "marked not deletable"))
        elif config.is_protected(item["path"]):
            refused.append((e, "protected location"))
        elif not os.path.exists(item["path"]):
            refused.append((e, "no longer exists"))
        elif _is_link(item["path"]):
            refused.append((e, "is a link/junction"))
        elif item["kind"] == "duplicate" and not os.path.exists(item.get("extra", {}).get("original", "")):
            refused.append((e, "the kept original copy is missing, refusing to remove the last copy"))
        else:
            accepted.append(item)
    return accepted, refused


def targets_for(item: dict) -> list[str]:
    """Cache roots are emptied, not removed (apps expect the folder to exist)."""
    p = item["path"]
    if item["kind"] == "cache" and item.get("extra", {}).get("category") == "cache" and os.path.isdir(p):
        return [os.path.join(p, n) for n in os.listdir(p)]
    return [p]


# ---------------------------------------------------------------- execution
def _default_trash(path: str) -> None:
    try:
        from send2trash import send2trash
    except ImportError as e:
        raise SystemExit("send2trash is required: pip install -r requirements.txt") from e
    send2trash(path)


def execute(items: list[dict], trash=_default_trash) -> list[dict]:
    """Move each target to the Recycle Bin. Returns one log record per target."""
    log: list[dict] = []
    for item in items:
        for t in targets_for(item):
            rec = {"item": item["name"], "path": t, "time": time.time()}
            try:
                size = dir_size(t) if os.path.isdir(t) else os.path.getsize(t)
                trash(os.path.abspath(t))
                rec.update(status="moved", size_bytes=size)
            except Exception as ex:   # locked/in-use files are expected; keep going
                rec.update(status="failed", error=str(ex))
            log.append(rec)
    return log


def _fmt(b: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or u == "TB":
            return f"{b:.2f} {u}" if u not in ("B", "KB") else f"{b:.0f} {u}"
        b /= 1024


def _find_selection(arg: str) -> Path | None:
    p = Path(arg)
    if p.exists():
        return p
    if p == config.SELECTION_FILE:   # default: fall back to the browser's Downloads copy
        cands = sorted((config.HOME / "Downloads").glob("selection*.json"), key=lambda x: x.stat().st_mtime)
        if cands:
            print(f"Using {cands[-1]} (newest selection in Downloads)")
            return cands[-1]
    return None


def run_clean(args) -> int:
    sel_path = _find_selection(args.selection)
    if sel_path is None:
        print("No selection file found. Export one from the report, or pass --selection <path>.")
        return 1
    if not config.SCAN_FILE.exists():
        print("No scan.json found. Run `python -m declutter scan` first.")
        return 1

    scan = json.loads(config.SCAN_FILE.read_text(encoding="utf-8"))
    scan_items = {os.path.normcase(os.path.abspath(i["path"])): i for i in scan["items"] if i["path"]}
    accepted, refused = validate(load_selection(sel_path), scan_items)

    # Recycle Bin capacity: Windows deletes things it cannot hold, so refuse those up front.
    if accepted:
        limit, nuke = recycle_bin_limit(accepted[0]["path"])
        if nuke:
            print("Recycle Bin is set to delete files immediately (NukeOnDelete). Refusing to continue.")
            return 1
        if limit:
            ok = []
            for it in accepted:
                if it["size_bytes"] > limit and not (it["kind"] == "cache" and it["extra"].get("category") == "cache"):
                    refused.append((it, f"larger than the Recycle Bin limit ({_fmt(limit)}); Windows would delete it permanently"))
                else:
                    ok.append(it)
            accepted = ok

    total = sum(i["size_bytes"] for i in accepted)
    print(f"\n{len(accepted)} item(s), {_fmt(total)} to move to the Recycle Bin:")
    for it in accepted:
        print(f"  {_fmt(it['size_bytes']):>10}  {it['path']}")
    if refused:
        print(f"\n{len(refused)} refused:")
        for e, why in refused:
            print(f"  {e.get('path', '?')}: {why}")

    if not accepted:
        return 0
    if not args.apply:
        print("\nDry run only. Re-run with --apply to move these to the Recycle Bin.")
        return 0
    if not args.yes and input("\nMove these to the Recycle Bin? [y/N] ").strip().lower() != "y":
        print("Cancelled.")
        return 0

    log = execute(accepted)
    moved = [r for r in log if r["status"] == "moved"]
    failed = [r for r in log if r["status"] == "failed"]
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    history = json.loads(config.CLEANUP_LOG.read_text(encoding="utf-8")) if config.CLEANUP_LOG.exists() else []
    config.CLEANUP_LOG.write_text(json.dumps(history + log, indent=2), encoding="utf-8")

    print(f"\nMoved {len(moved)} to the Recycle Bin ({_fmt(sum(r['size_bytes'] for r in moved))}); {len(failed)} failed.")
    for r in failed:
        print(f"  failed: {r['path']}: {r['error']}")
    print("Disk space is only freed once you empty the Recycle Bin. Log: " + str(config.CLEANUP_LOG))
    return 0 if not failed else 2
