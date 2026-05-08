"""Portfolio discovery helpers for ETF-derived candidate universes."""

from __future__ import annotations

from typing import Any


def combine_etf_holdings(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        if payload.get("status") != "ok":
            continue
        etf = payload.get("etf", "")
        for holding in payload.get("holdings", []):
            ticker = str(holding.get("ticker", "")).upper().strip()
            if not ticker:
                continue
            row = combined.setdefault(
                ticker,
                {
                    "ticker": ticker,
                    "company": holding.get("company") or ticker,
                    "etfs": [],
                    "etf_count": 0,
                    "combined_etf_weight": 0.0,
                },
            )
            if etf and etf not in row["etfs"]:
                row["etfs"].append(etf)
            row["etf_count"] = len(row["etfs"])
            row["combined_etf_weight"] += float(holding.get("holding_percent") or 0.0)
    return sorted(
        combined.values(),
        key=lambda row: (row["etf_count"], row["combined_etf_weight"], row["ticker"]),
        reverse=True,
    )


def portfolio_rank(row: dict[str, Any]) -> tuple[int, int, float, int, str]:
    verdict_order = {"PASS": 2, "REVIEW NEEDED": 1, "FAIL": 0}
    confidence_order = {"High": 2, "Medium": 1, "Low": 0}
    return (
        int(row.get("etf_count") or 0),
        verdict_order.get(row.get("verdict"), 0),
        float(row.get("combined_etf_weight") or 0.0),
        confidence_order.get(row.get("confidence"), 0),
        str(row.get("ticker", "")),
    )


def sort_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=portfolio_rank, reverse=True)


def build_equal_weight_portfolio(
    rows: list[dict[str, Any]], max_positions: int = 15, include_review: bool = False
) -> list[dict[str, Any]]:
    eligible_statuses = {"PASS", "REVIEW NEEDED"} if include_review else {"PASS"}
    eligible = [row for row in sort_candidates(rows) if row.get("verdict") in eligible_statuses]
    eligible = [row for row in eligible if row.get("verdict") != "FAIL"]
    selected = eligible[: max(1, int(max_positions))]
    if not selected:
        return []
    weight = 1 / len(selected)
    return [{**row, "portfolio_weight": weight} for row in selected]
