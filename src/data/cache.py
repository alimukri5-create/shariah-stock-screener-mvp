"""Small JSON cache for public data responses."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from src.config import CACHE_DIR, DEFAULT_CACHE_TTL_SECONDS


class JsonCache:
    def __init__(self, cache_dir: Path = CACHE_DIR, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe_key = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in key)
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str, refresh: bool = False) -> Any | None:
        if refresh:
            return None
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            timestamp = float(payload.get("timestamp", 0))
            if time.time() - timestamp > self.ttl_seconds:
                return None
            return payload.get("data")
        except Exception:
            return None

    def get_stale(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("data")
        except Exception:
            return None

    def set(self, key: str, data: Any) -> None:
        path = self._path(key)
        payload = {"timestamp": time.time(), "data": data}
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def clear(self) -> None:
        for path in self.cache_dir.glob("*.json"):
            try:
                path.unlink()
            except OSError:
                continue
