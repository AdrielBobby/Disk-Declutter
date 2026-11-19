import json
import re

from declutter.report import render_html


def _extract(html: str) -> dict:
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    return json.loads(m.group(1).replace("<\\/", "</"))


def test_embedded_data_round_trips():
    scan = {"items": [{"name": "a", "path": "C:\\x"}], "usage_tree": None, "scanned_at": 1.0, "errors": []}
    assert _extract(render_html(scan)) == scan


def test_hostile_path_cannot_break_out_of_script_tag():
    evil = "C:\\</script><script>alert(1)</script>"
    scan = {"items": [{"name": evil, "path": evil}], "usage_tree": None, "scanned_at": 1.0, "errors": []}
    html = render_html(scan)
    assert html.count("</script>") == 2   # only the template's own closing tags
    assert _extract(html)["items"][0]["name"] == evil
