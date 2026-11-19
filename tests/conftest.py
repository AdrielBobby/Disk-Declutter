import pytest

from declutter import config


@pytest.fixture(autouse=True)
def _no_hash_cache(monkeypatch):
    """Keep tests from reading/writing output/hash_cache.json in the working directory."""
    monkeypatch.setattr(config, "HASH_CACHE", None)
