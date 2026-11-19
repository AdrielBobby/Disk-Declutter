import json
import os

from declutter import clean, config


def _item(path, kind="file", size=10, deletable=True, **extra):
    return {"kind": kind, "name": os.path.basename(path), "path": str(path), "size_bytes": size,
            "deletable": deletable, "extra": extra}


def _index(*items):
    return {os.path.normcase(os.path.abspath(i["path"])): i for i in items}


def test_path_not_in_scan_is_refused(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"1")
    accepted, refused = clean.validate([{"path": str(f)}], {})
    assert not accepted and "not found" in refused[0][1]


def test_apps_and_nondeletable_and_protected_refused(tmp_path):
    a = tmp_path / "app"; a.mkdir()
    b = tmp_path / "locked.bin"; b.write_bytes(b"1")
    sysfile = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "notepad.exe")
    items = [_item(a, "app"), _item(b, deletable=False), _item(sysfile)]
    accepted, refused = clean.validate([{"path": i["path"]} for i in items], _index(*items))
    assert not accepted
    assert [r[1] for r in refused] == ["apps must be uninstalled by you", "marked not deletable", "protected location"]


def test_duplicate_requires_original_to_exist(tmp_path):
    dup = tmp_path / "copy.bin"; dup.write_bytes(b"1")
    orig = tmp_path / "orig.bin"
    it = _item(dup, "duplicate", original=str(orig))
    accepted, refused = clean.validate([{"path": str(dup)}], _index(it))
    assert not accepted and "original" in refused[0][1]
    orig.write_bytes(b"1")
    accepted, _ = clean.validate([{"path": str(dup)}], _index(it))
    assert len(accepted) == 1


def test_duplicate_selection_entries_counted_once(tmp_path):
    f = tmp_path / "x.bin"; f.write_bytes(b"1")
    it = _item(f)
    accepted, _ = clean.validate([{"path": str(f)}, {"path": str(f)}], _index(it))
    assert len(accepted) == 1


def test_cache_root_is_emptied_not_removed(tmp_path):
    cache = tmp_path / "cache"; cache.mkdir()
    (cache / "a.tmp").write_bytes(b"1")
    (cache / "sub").mkdir()
    it = _item(cache, "cache", category="cache")
    assert sorted(os.path.basename(t) for t in clean.targets_for(it)) == ["a.tmp", "sub"]
    nm = _item(cache, "cache", category="node_modules")
    assert clean.targets_for(nm) == [str(cache)]


def test_execute_logs_success_and_failure_and_continues(tmp_path):
    ok = tmp_path / "ok.bin"; ok.write_bytes(b"1" * 5)
    bad = tmp_path / "bad.bin"; bad.write_bytes(b"1")
    seen = []

    def fake_trash(p):
        if p.endswith("bad.bin"):
            raise PermissionError("in use")
        seen.append(p)

    log = clean.execute([_item(bad), _item(ok)], trash=fake_trash)
    assert [r["status"] for r in log] == ["failed", "moved"]
    assert log[1]["size_bytes"] == 5 and "in use" in log[0]["error"]
    assert len(seen) == 1


def test_dry_run_never_touches_files(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(config, "SCAN_FILE", tmp_path / "scan.json")
    f = tmp_path / "victim.bin"; f.write_bytes(b"1")
    config.SCAN_FILE.write_text(json.dumps({"items": [_item(f)]}))
    sel = tmp_path / "sel.json"
    sel.write_text(json.dumps({"items": [{"path": str(f)}]}))
    monkeypatch.setattr(clean, "execute", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))

    class Args:
        selection = str(sel); apply = False; yes = False

    assert clean.run_clean(Args) == 0
    assert f.exists()
