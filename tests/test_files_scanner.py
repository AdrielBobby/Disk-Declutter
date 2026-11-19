import os
import time

from declutter.models import DUPLICATE, FILE
from declutter.scanners import files
from declutter.scoring import score_items

MB = 1024 * 1024


def _make(path, size, age_days=0, content=None):
    data = content if content is not None else os.urandom(size)
    path.write_bytes(data)
    t = time.time() - age_days * 86400
    os.utime(path, (t, t))
    return path


def test_finds_old_large_file_and_ignores_recent_and_small(tmp_path):
    _make(tmp_path / "old_big.iso", 2 * MB, age_days=400)
    _make(tmp_path / "new_big.iso", 2 * MB, age_days=1)
    _make(tmp_path / "old_small.iso", 10, age_days=400)
    errors = []
    items = files.scan([str(tmp_path)], min_size_mb=1, stale_days=180, errors=errors)
    names = {i.name for i in items}
    assert names == {"old_big.iso"}
    assert items[0].kind == FILE


def test_detects_duplicates_and_keeps_oldest(tmp_path):
    blob = os.urandom(2 * MB)
    _make(tmp_path / "a.bin", 0, age_days=50, content=blob)
    (tmp_path / "sub").mkdir()
    _make(tmp_path / "sub" / "copy.bin", 0, age_days=5, content=blob)
    # same size, different content: must NOT be a duplicate
    _make(tmp_path / "other.bin", 2 * MB, age_days=5)
    items = files.scan([str(tmp_path)], min_size_mb=500, stale_days=180, errors=[])
    dups = [i for i in items if i.kind == DUPLICATE]
    assert [d.name for d in dups] == ["copy.bin"]
    assert dups[0].extra["original"].endswith("a.bin")


def test_scoring_marks_disposable_higher_than_personal(tmp_path):
    _make(tmp_path / "setup.exe", 2 * MB, age_days=500)
    _make(tmp_path / "thesis.docx", 2 * MB, age_days=500)
    items = files.scan([str(tmp_path)], min_size_mb=1, stale_days=180, errors=[])
    score_items(items, 180)
    by_name = {i.name: i for i in items}
    assert by_name["setup.exe"].confidence > by_name["thesis.docx"].confidence
    assert by_name["thesis.docx"].risk == "high"


def test_hash_cache_skips_rehashing_unchanged_files(tmp_path, monkeypatch):
    blob = os.urandom(2 * MB)
    _make(tmp_path / "a.bin", 0, age_days=50, content=blob)
    _make(tmp_path / "b.bin", 0, age_days=5, content=blob)
    cache_file = tmp_path / "out" / "hash_cache.json"
    monkeypatch.setattr(files.config, "HASH_CACHE", cache_file)

    first = files.scan([str(tmp_path)], min_size_mb=500, stale_days=180, errors=[])
    assert cache_file.exists()

    calls = []
    real = files._hash_file
    monkeypatch.setattr(files, "_hash_file", lambda *a: calls.append(a) or real(*a))
    second = files.scan([str(tmp_path)], min_size_mb=500, stale_days=180, errors=[])
    assert calls == []                                   # everything came from the cache
    assert [i.name for i in second] == [i.name for i in first] == ["b.bin"]

    # touching a file invalidates only its entry
    t = time.time() + 10
    os.utime(tmp_path / "b.bin", (t, t))
    files.scan([str(tmp_path)], min_size_mb=500, stale_days=180, errors=[])
    assert len(calls) == 2                               # partial + full hash for b.bin only


def test_junctions_are_skipped(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    _make(real / "big.iso", 2 * MB, age_days=400)
    link = tmp_path / "link"
    try:
        os.symlink(real, link, target_is_directory=True)
    except OSError:
        import subprocess
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(real)], capture_output=True)
        if r.returncode != 0:
            return  # cannot create links here; nothing to verify
    items = files.scan([str(tmp_path)], min_size_mb=1, stale_days=180, errors=[])
    assert len(items) == 1


def test_overlapping_roots_do_not_double_count(tmp_path):
    _make(tmp_path / "x.iso", 2 * MB, age_days=400)
    items = files.scan([str(tmp_path), str(tmp_path)], min_size_mb=1, stale_days=180, errors=[])
    assert len(items) == 1
