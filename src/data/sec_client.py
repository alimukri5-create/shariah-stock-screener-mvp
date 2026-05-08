"""SEC EDGAR client."""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from src.config import (
    DEFAULT_SEC_USER_AGENT,
    SEC_COMPANY_FACTS_URL,
    SEC_SUBMISSIONS_URL,
    SEC_TICKER_URL,
)
from src.data.cache import JsonCache


class SecClient:
    def __init__(self, cache: JsonCache | None = None) -> None:
        self.cache = cache or JsonCache()
        self.session = requests.Session()
        self.session.trust_env = False

    @staticmethod
    def headers() -> dict[str, str]:
        return {
            "User-Agent": os.getenv("SEC_USER_AGENT", DEFAULT_SEC_USER_AGENT),
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

    def _get_json(self, url: str, key: str, refresh: bool = False) -> Any:
        cached = self.cache.get(key, refresh=refresh)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.get(url, headers=self.headers(), timeout=20)
                if response.status_code == 429:
                    time.sleep(1.5 + attempt)
                    continue
                response.raise_for_status()
                data = response.json()
                self.cache.set(key, data)
                return data
            except Exception as error:
                last_error = error
                if attempt < 2:
                    time.sleep(0.75 + attempt)
        stale = self.cache.get_stale(key)
        if stale is not None:
            return stale
        raise RuntimeError(f"SEC request failed for {url}: {last_error}")

    def ticker_to_cik(self, ticker: str, refresh: bool = False) -> dict[str, Any] | None:
        mapping = self._get_json(SEC_TICKER_URL, "sec_ticker_mapping", refresh=refresh)
        ticker_upper = ticker.upper().strip()
        if not isinstance(mapping, dict):
            return None
        for item in mapping.values():
            if str(item.get("ticker", "")).upper() == ticker_upper:
                cik = str(item.get("cik_str", "")).zfill(10)
                return {"ticker": ticker_upper, "cik": cik, "company_name": item.get("title")}
        return None

    def get_company_submissions(self, cik: str, refresh: bool = False) -> dict[str, Any]:
        return self._get_json(
            SEC_SUBMISSIONS_URL.format(cik=cik),
            f"sec_submissions_{cik}",
            refresh=refresh,
        )

    def get_company_facts(self, cik: str, refresh: bool = False) -> dict[str, Any]:
        return self._get_json(
            SEC_COMPANY_FACTS_URL.format(cik=cik),
            f"sec_company_facts_{cik}",
            refresh=refresh,
        )
