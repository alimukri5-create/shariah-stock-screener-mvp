"""Optional unofficial yfinance fallback."""

from __future__ import annotations

import os
from typing import Any

from src.config import CACHE_DIR
from src.data.cache import JsonCache


YFINANCE_CACHE_VERSION = 2


def _latest_statement_value(statement: Any, labels: list[str]) -> tuple[float | None, dict[str, Any] | None]:
    try:
        if statement is None or statement.empty:
            return None, None
        for label in labels:
            if label not in statement.index:
                continue
            series = statement.loc[label].dropna()
            if series.empty:
                continue
            date = series.index[0]
            return float(series.iloc[0]), {"label": label, "period": str(date.date() if hasattr(date, "date") else date)}
    except Exception:
        return None, None
    return None, None


class YFinanceClient:
    def __init__(self, cache: JsonCache | None = None) -> None:
        self.cache = cache or JsonCache()

    def get_profile(self, ticker: str, refresh: bool = False) -> dict[str, Any]:
        key = f"yfinance_{ticker.upper()}"
        cached = self.cache.get(key, refresh=refresh)
        if cached is not None and cached.get("cache_version") == YFINANCE_CACHE_VERSION:
            return cached

        try:
            import yfinance as yf

            yf_cache_dir = CACHE_DIR / "yfinance_runtime"
            yf_cache_dir.mkdir(parents=True, exist_ok=True)
            yf.set_tz_cache_location(str(yf_cache_dir))
            proxy_vars = [
                "HTTP_PROXY",
                "HTTPS_PROXY",
                "ALL_PROXY",
                "http_proxy",
                "https_proxy",
                "all_proxy",
            ]
            saved_proxy_env = {name: os.environ.pop(name, None) for name in proxy_vars}
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            balance_sheet = stock.balance_sheet
            income_stmt = stock.income_stmt
        except Exception as error:
            stale = self.cache.get_stale(key)
            if stale is not None:
                stale["warning"] = f"Using stale yfinance fallback cache because live yfinance failed: {error}"
                return stale
            return {"status": "error", "error": str(error), "source": "yfinance unofficial fallback"}
        finally:
            if "saved_proxy_env" in locals():
                for name, value in saved_proxy_env.items():
                    if value is not None:
                        os.environ[name] = value

        market_cap = info.get("marketCap")
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
        if market_cap is None and price and shares:
            market_cap = float(price) * float(shares)

        total_debt, total_debt_field = _latest_statement_value(
            balance_sheet,
            ["Total Debt", "Current Debt And Capital Lease Obligation", "Long Term Debt And Capital Lease Obligation"],
        )
        cash, cash_field = _latest_statement_value(
            balance_sheet,
            ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
        )
        cash_and_sti, cash_and_sti_field = _latest_statement_value(
            balance_sheet,
            ["Cash Cash Equivalents And Short Term Investments"],
        )
        marketable_securities = None
        marketable_securities_field = None
        if cash_and_sti is not None and cash is not None and cash_and_sti >= cash:
            marketable_securities = cash_and_sti - cash
            marketable_securities_field = cash_and_sti_field
        revenue, revenue_field = _latest_statement_value(
            income_stmt,
            ["Total Revenue", "Operating Revenue"],
        )
        non_perm, non_perm_field = _latest_statement_value(
            income_stmt,
            ["Interest Income", "Investment Income Interest", "Net Non Operating Interest Income Expense"],
        )

        data = {
            "status": "ok",
            "cache_version": YFINANCE_CACHE_VERSION,
            "source": "yfinance unofficial fallback",
            "market_cap": market_cap,
            "price": price,
            "shares_outstanding": shares,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "description": info.get("longBusinessSummary"),
            "company_name": info.get("longName") or info.get("shortName"),
            "quote_type": info.get("quoteType"),
            "financials": {
                "total_interest_bearing_debt": total_debt,
                "cash_and_equivalents": cash,
                "marketable_securities": marketable_securities,
                "total_revenue": revenue,
                "non_permissible_income": non_perm,
                "source_fields": {
                    "total_interest_bearing_debt": total_debt_field,
                    "cash_and_equivalents": cash_field,
                    "marketable_securities": marketable_securities_field,
                    "total_revenue": revenue_field,
                    "non_permissible_income": non_perm_field,
                },
            },
        }
        self.cache.set(key, data)
        return data
