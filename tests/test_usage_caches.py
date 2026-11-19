import os
import time

from declutter import config
from declutter.fsutil import dir_size
from declutter.scanners import caches, usage

MB = 1024 * 1024


def test_dir_size_sums_nested_files(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.bin").write_bytes(b"1" * 1000)
    (tmp_path / "y.bin").write_bytes(b"1" * 500)
    assert dir_size(str(tmp_path)) == 1500


def test_usage_tree_rolls_up_sizes(tmp_path):
    (tmp_path / "big" / "deep").mkdir(parents=True)
    (tmp_path / "big" / "deep" / "f.bin").write_bytes(b"1" * 3000)
    (tmp_path / "small").mkdir()
    (tmp_path / "small" / "g.bin").write_bytes(b"1" * 10)
    tree = usage.scan([], root=str(tmp_path))
    assert tree["size"] == 3010
    assert tree["children"][0]["name"] == "big"
    assert tree["children"][0]["size"] == 3000


def test_stale_node_modules_found_and_recent_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(caches, "MIN_BYTES", 1000)
    monkeypatch.setattr(caches, "_known_locations", lambda: [])

    old = tmp_path / "oldproj"
    (old / "node_modules" / "pkg").mkdir(parents=True)
    (old / "node_modules" / "pkg" / "i.js").write_bytes(b"1" * 5000)
    new = tmp_path / "newproj"
    (new / "node_modules").mkdir(parents=True)
    (new / "node_modules" / "i.js").write_bytes(b"1" * 5000)

    t = time.time() - 200 * 86400
    for p in (old / "node_modules" / "pkg", old / "node_modules", old):
        os.utime(p, (t, t))

    items = caches.scan([], stale_days=90)
    assert [i.name for i in items] == ["node_modules (oldproj)"]
