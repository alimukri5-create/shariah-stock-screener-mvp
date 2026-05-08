"""Display formatting helpers."""

from __future__ import annotations


def money(value: float | None) -> str:
    if value is None:
        return "Unavailable"
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs_value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    return f"${value:,.0f}"


def percent(value: float | None) -> str:
    return "Unavailable" if value is None else f"{value:.1%}"


def clean_ticker(value: str) -> str:
    return "".join(ch for ch in value.upper().strip() if ch.isalnum() or ch in {".", "-"})

