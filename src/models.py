"""Typed models for AmanahScreen."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RuleStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_NEEDED = "REVIEW NEEDED"


class Confidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class CompanyProfile(BaseModel):
    ticker: str
    company_name: str | None = None
    cik: str | None = None
    sic: str | None = None
    sic_description: str | None = None
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    source: list[str] = Field(default_factory=list)
    as_of_date: str | None = None


class FinancialSnapshot(BaseModel):
    market_cap: float | None = None
    total_interest_bearing_debt: float | None = None
    cash_and_equivalents: float | None = None
    marketable_securities: float | None = None
    total_revenue: float | None = None
    non_permissible_income: float | None = None
    fiscal_period: str | None = None
    fiscal_year: int | None = None
    source_fields: dict[str, Any] = Field(default_factory=dict)
    source: list[str] = Field(default_factory=list)
    as_of_date: str | None = None


class ScreeningRuleResult(BaseModel):
    rule_id: str
    rule_name: str
    category: str
    status: RuleStatus
    threshold: float | None = None
    observed_value: float | None = None
    numerator: float | None = None
    denominator: float | None = None
    reason: str
    source_detail: str | None = None
    source: list[str] = Field(default_factory=list)
    as_of_date: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence.LOW


class ScreeningStandard(BaseModel):
    name: str
    debt_threshold: float = 0.30
    cash_securities_threshold: float = 0.30
    non_permissible_income_threshold: float = 0.05
    include_finance_leases: bool = False
    conservative_mode: bool = True
    use_yfinance_financial_fallback: bool = True


class ScreeningVerdict(BaseModel):
    ticker: str
    company_name: str | None = None
    verdict: RuleStatus
    confidence: Confidence
    one_sentence_summary: str
    rule_results: list[ScreeningRuleResult]
    data_sources: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
