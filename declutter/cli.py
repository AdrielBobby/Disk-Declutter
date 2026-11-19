"""Command-line entry point: scan -> report -> clean."""

from __future__ import annotations

import argparse
import sys

from . import __version__, config


def _add_scan_args(s: argparse.ArgumentParser) -> None:
    s.add_argument("--dirs", nargs="*", help="Folders to scan (default: Downloads, Documents, Desktop, ...)")
    s.add_argument("--min-size-mb", type=int, default=config.MIN_SIZE_MB)
    s.add_argument("--stale-days", type=int, default=config.STALE_DAYS)
    s.add_argument("--skip", nargs="*", default=[], choices=["files", "apps", "caches", "usage"],
                   help="Scanners to skip")
    s.add_argument("--ai", action="store_true", help="Ask a local Ollama model about borderline items")
    s.add_argument("--model", default=config.OLLAMA_MODEL)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="declutter",
        description="Find unused apps, stale files and junk that can be cleared to save space.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="Scan the machine (read-only) and write output/scan.json")
    _add_scan_args(s)

    g = sub.add_parser("go", help="Do everything: scan, open the report, then clean what you select")
    _add_scan_args(g)

    r = sub.add_parser("report", help="Render output/scan.json into output/report.html")
    r.add_argument("--open", action="store_true", help="Open the report in the browser")

    c = sub.add_parser("clean", help="Send items from output/selection.json to the Recycle Bin")
    c.add_argument("--selection", default=str(config.SELECTION_FILE))
    c.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    c.add_argument("--apply", action="store_true", help="Actually move items (default is a dry run)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "scan":
        from .scan import run_scan
        return run_scan(args)
    if args.command == "go":
        from .go import run_go
        return run_go(args)
    if args.command == "report":
        from .report import run_report
        return run_report(args)
    if args.command == "clean":
        from .clean import run_clean
        return run_clean(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
