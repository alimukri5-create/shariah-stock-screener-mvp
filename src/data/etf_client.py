"""Halal ETF holdings discovery through free unofficial yfinance data."""

from __future__ import annotations

import os
from typing import Any

from src.config import CACHE_DIR
from src.data.cache import JsonCache


ETF_HOLDINGS_CACHE_VERSION = 1

HALAL_ETFS: dict[str, str] = {
    "SPUS": "SP Funds S&P 500 Sharia Industry Exclusions ETF",
    "HLAL": "Wahed FTSE USA Shariah ETF",
    "UMMA": "Wahed Dow Jones Islamic World ETF",
    "SPRE": "SP Funds S&P Global REIT Sharia ETF",
    "SPSK": "SP Funds Dow Jones Global Sukuk ETF",
}


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


class EtfHoldingsClient:
    """Fetch ETF top holdings without API keys.

    yfinance is unofficial, so this client is only used as a discovery source.
    Every response is labelled accordingly and cached locally.
    """

    def __init__(self, cache: JsonCache | None = None) -> None:
        self.cache = cache or JsonCache()

    def get_holdings(self, ticker: str, limit: int = 25, refresh: bool = False) -> dict[str, Any]:
        ticker = ticker.upper().strip()
        limit = max(1, min(int(limit), 50))
        key = f"etf_holdings_{ticker}_{limit}"
        cached = self.cache.get(key, refresh=refresh)
        if cached is not None and cached.get("cache_version") == ETF_HOLDINGS_CACHE_VERSION:
            return cached

        try:
            import yfinance as yf

            yf_cache_dir = CACHE_DIR / "yfinance_runtime"
            yf_cache_dir.mkdir(parents=True, exist_ok=True)
            yf.set_tz_cache_location(str(yf_cache_dir))
            proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]
            saved_proxy_env = {name: os.environ.pop(name, None) for name in proxy_vars}

            fund = yf.Ticker(ticker)
            funds_data = fund.funds_data
            top_holdings = funds_data.top_holdings
            fund_overview = getattr(funds_data, "fund_overview", {}) or {}
        except Exception as error:
            stale = self.cache.get_stale(key)
            if stale is not None:
                stale["warning"] = f"Using stale ETF holdings cache because live yfinance failed: {error}"
                return stale
            return {
                "status": "error",
                "cache_version": ETF_HOLDINGS_CACHE_VERSION,
                "etf": ticker,
                "name": HALAL_ETFS.get(ticker, ticker),
                "holdings": [],
                "source": "yfinance ETF holdings unofficial fallback",
                "error": str(error),
            }
        finally:
            if "saved_proxy_env" in locals():
                for name, value in saved_proxy_env.items():
                    if value is not None:
                        os.environ[name] = value

        holdings: list[dict[str, Any]] = []
        if top_holdings is not None and not top_holdings.empty:
            for symbol, row in top_holdings.head(limit).iterrows():
                holding_ticker = str(symbol).strip().upper()
                if not holding_ticker or holding_ticker == "NAN":
                    continue
                holdings.append(
                    {
                        "ticker": holding_ticker,
                        "company": str(row.get("Name") or holding_ticker),
                        "holding_percent": _as_float(row.get("Holding Percent")),
                    }
                )

        status = "ok" if holdings else "empty"
        note = None if holdings else "No equity top holdings were exposed by yfinance for this fund."
        data = {
            "status": status,
            "cache_version": ETF_HOLDINGS_CACHE_VERSION,
            "etf": ticker,
            "name": HALAL_ETFS.get(ticker, ticker),
            "holdings": holdings,
            "source": "yfinance ETF holdings unofficial fallback",
            "category": fund_overview.get("categoryName"),
            "family": fund_overview.get("family"),
            "note": note,
        }
        self.cache.set(key, data)
        return data
