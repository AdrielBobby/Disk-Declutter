"""Render scan.json into a self-contained interactive HTML report."""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path

from . import config

TEMPLATE = Path(__file__).parent / "templates" / "report.html"


def render_html(scan: dict) -> str:
    """Embed scan data in the template. '</' is escaped so paths can't close the script tag."""
    payload = json.dumps(scan).replace("</", "<\\/").replace("<!--", "<\\!--")
    return TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload)


def run_report(args) -> int:
    if not config.SCAN_FILE.exists():
        print(f"No scan found at {config.SCAN_FILE}. Run `python -m declutter scan` first.")
        return 1
    scan = json.loads(config.SCAN_FILE.read_text(encoding="utf-8"))
    config.OUTPUT_DIR.mkdir(exist_ok=True)
    config.REPORT_FILE.write_text(render_html(scan), encoding="utf-8")
    print(f"Report written to {config.REPORT_FILE.resolve()}")
    if args.open:
        webbrowser.open(config.REPORT_FILE.resolve().as_uri())
    return 0
