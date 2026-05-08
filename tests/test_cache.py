from uuid import uuid4
from pathlib import Path

from src.data.cache import JsonCache


def cache_dir(name: str) -> Path:
    path = Path(__file__).resolve().parents[1] / "data_cache" / f"{name}_{uuid4().hex}"
    path.mkdir(parents=True)
    return path


def test_cache_read_write():
    cache = JsonCache(cache_dir("test_read_write"), ttl_seconds=60)
    cache.set("hello/world", {"ok": True})
    assert cache.get("hello/world") == {"ok": True}


def test_cache_refresh_bypasses():
    cache = JsonCache(cache_dir("test_refresh"), ttl_seconds=60)
    cache.set("key", {"ok": True})
    assert cache.get("key", refresh=True) is None


def test_cache_corrupt_file_returns_none():
    cache = JsonCache(cache_dir("test_corrupt"), ttl_seconds=60)
    cache._path("bad").write_text("{not json", encoding="utf-8")
    assert cache.get("bad") is None
