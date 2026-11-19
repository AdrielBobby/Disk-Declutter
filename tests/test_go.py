import json
import os
import time

from declutter import clean, config, go


def test_newest_selection_ignores_old_files(tmp_path, monkeypatch):
    out = tmp_path / "out"; out.mkdir()
    monkeypatch.setattr(config, "OUTPUT_DIR", out)
    monkeypatch.setattr(config, "HOME", tmp_path)
    (tmp_path / "Downloads").mkdir()
    stale = out / "selection.json"; stale.write_text("{}")
    os.utime(stale, (1000, 1000))
    assert go.newest_selection(time.time() - 5) is None          # old test file is not picked up

    fresh = tmp_path / "Downloads" / "selection (1).json"; fresh.write_text("{}")
    assert go.newest_selection(time.time() - 5) == fresh


def test_quit_changes_nothing(monkeypatch):
    monkeypatch.setattr("declutter.scan.run_scan", lambda a: 0)
    monkeypatch.setattr("declutter.report.run_report", lambda a: 0)
    monkeypatch.setattr(clean, "run_clean", lambda a: (_ for _ in ()).throw(AssertionError("must not clean")))
    monkeypatch.setattr("builtins.input", lambda *_: "q")
    assert go.run_go(object()) == 0


def test_cleaning_asks_for_confirmation(monkeypatch, tmp_path):
    sel = tmp_path / "sel.json"; sel.write_text(json.dumps({"items": []}))
    seen = {}
    monkeypatch.setattr("declutter.scan.run_scan", lambda a: 0)
    monkeypatch.setattr("declutter.report.run_report", lambda a: 0)
    monkeypatch.setattr(go, "newest_selection", lambda since: sel)
    monkeypatch.setattr(clean, "run_clean", lambda a: seen.update(apply=a.apply, yes=a.yes) or 0)
    monkeypatch.setattr("builtins.input", lambda *_: "")
    go.run_go(object())
    assert seen == {"apply": True, "yes": False}                 # still prompts before moving anything
