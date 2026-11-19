import os
import time

from declutter.models import APP
from declutter.scanners import apps
from declutter.scoring import score_items


def test_prefetch_map_takes_newest_per_exe(tmp_path):
    a = tmp_path / "GAME.EXE-AAAA1111.pf"
    b = tmp_path / "GAME.EXE-BBBB2222.pf"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    os.utime(a, (1000, 1000))
    os.utime(b, (5000, 5000))
    m = apps.prefetch_map(str(tmp_path), [])
    assert m["GAME.EXE"] == 5000


def test_prefetch_unreadable_is_reported_not_fatal(tmp_path):
    errors = []
    assert apps.prefetch_map(str(tmp_path / "missing"), errors) == {}
    assert errors


def test_last_used_prefers_prefetch(tmp_path):
    (tmp_path / "app.exe").write_bytes(b"x")
    ts, src = apps.last_used(str(tmp_path), "20200101", {"APP.EXE": 12345.0})
    assert (ts, src) == (12345.0, "prefetch")


def test_last_used_falls_back_to_install_date():
    ts, src = apps.last_used(None, "20200101", {})
    assert src == "install_date" and ts is not None


def test_entry_filters_and_builds_item(tmp_path):
    big = {"DisplayName": "Big App", "EstimatedSize": 500 * 1024, "UninstallString": "uninst.exe",
           "InstallDate": "20200101"}
    item = apps.entry_to_item(big, {}, [])
    assert item.kind == APP and item.deletable is False and item.uninstall_cmd == "uninst.exe"
    assert apps.entry_to_item({"DisplayName": "Tiny", "EstimatedSize": 10}, {}, []) is None
    assert apps.entry_to_item({"DisplayName": "Sys", "SystemComponent": 1, "EstimatedSize": 10**7}, {}, []) is None
    assert apps.entry_to_item({"DisplayName": "Security Update for X", "EstimatedSize": 10**7}, {}, []) is None


def test_scoring_weak_evidence_is_less_confident_than_prefetch():
    old = time.time() - 400 * 86400
    strong = apps.entry_to_item({"DisplayName": "A", "EstimatedSize": 10**6}, {}, [])
    strong.last_used, strong.last_used_source = old, "prefetch"
    weak = apps.entry_to_item({"DisplayName": "B", "EstimatedSize": 10**6}, {}, [])
    weak.last_used, weak.last_used_source = old, "install_date"
    score_items([strong, weak], 180)
    assert strong.confidence > weak.confidence
    assert not strong.deletable
