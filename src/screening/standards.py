"""Configurable screening standards."""

from __future__ import annotations

from src.models import ScreeningStandard


def get_standard(name: str = "AAOIFI-style") -> ScreeningStandard:
    if name == "FTSE-style placeholder":
        return ScreeningStandard(
            name="FTSE-style placeholder",
            debt_threshold=0.33,
            cash_securities_threshold=0.33,
            non_permissible_income_threshold=0.05,
            include_finance_leases=False,
            conservative_mode=True,
        )
    return ScreeningStandard(name="AAOIFI-style")


def available_standards() -> list[str]:
    return ["AAOIFI-style", "FTSE-style placeholder"]

