"""Normalize SEC and yfinance data into screening models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.models import CompanyProfile, FinancialSnapshot


DEBT_TAGS = [
    "DebtCurrent",
    "LongTermDebt",
    "ShortTermBorrowings",
    "LongTermDebtCurrent",
    "LongTermDebtNoncurrent",
    "ShortTermDebt",
    "NotesPayable",
    "CommercialPaper",
    "CurrentPortionOfLongTermDebt",
]
CURRENT_DEBT_TAGS = [
    "DebtCurrent",
    "ShortTermBorrowings",
    "ShortTermDebt",
    "CurrentPortionOfLongTermDebt",
    "LongTermDebtCurrent",
    "CommercialPaper",
]
NONCURRENT_DEBT_TAGS = [
    "LongTermDebt",
    "LongTermDebtNoncurrent",
    "NotesPayable",
]
LEASE_TAGS = [
    "FinanceLeaseLiability",
    "FinanceLeaseLiabilityCurrent",
    "FinanceLeaseLiabilityNoncurrent",
]
CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    "Cash",
    "CashEquivalentsAtCarryingValue",
]
SECURITIES_TAGS = [
    "ShortTermInvestments",
    "MarketableSecuritiesCurrent",
    "AvailableForSaleSecuritiesCurrent",
    "DebtSecuritiesAvailableForSaleCurrent",
]
REVENUE_TAGS = [
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet",
]
NON_PERMISSIBLE_TAGS = [
    "InterestIncomeExpenseNonOperatingNet",
    "InterestIncomeExpenseNonoperatingNet",
    "InterestIncomeNonOperating",
    "InterestIncomeNonoperating",
    "InterestIncomeOther",
    "InterestIncomeShortTermInvestmentOther",
    "InvestmentIncomeInterest",
    "InvestmentIncomeInterestAndDividend",
    "InvestmentIncomeNet",
    "InterestAndDividendIncomeOperating",
    "InterestIncomeOperating",
    "InterestRevenueExpenseNet",
]


def extract_company_profile(
    ticker: str,
    cik_result: dict[str, Any] | None,
    submissions: dict[str, Any] | None,
    yfinance_data: dict[str, Any] | None,
) -> CompanyProfile:
    submissions = submissions or {}
    yfinance_data = yfinance_data or {}
    sources = []
    if submissions:
        sources.append("SEC EDGAR")
    if yfinance_data.get("status") == "ok":
        sources.append("yfinance unofficial fallback")

    return CompanyProfile(
        ticker=ticker.upper(),
        company_name=submissions.get("name") or (cik_result or {}).get("company_name") or yfinance_data.get("company_name"),
        cik=(cik_result or {}).get("cik"),
        sic=str(submissions.get("sic", "") or "") or None,
        sic_description=submissions.get("sicDescription"),
        sector=yfinance_data.get("sector"),
        industry=yfinance_data.get("industry"),
        description=yfinance_data.get("description"),
        source=sources or ["automatic source unavailable"],
        as_of_date=datetime.now(UTC).date().isoformat(),
    )


def _facts(company_facts: dict[str, Any]) -> dict[str, Any]:
    return company_facts.get("facts", {}).get("us-gaap", {}) if isinstance(company_facts, dict) else {}


def _latest_item(concept: dict[str, Any], annual: bool = True) -> dict[str, Any] | None:
    units = concept.get("units", {})
    items = units.get("USD") or units.get("shares") or []
    if not isinstance(items, list):
        return None
    forms = {"10-K", "20-F", "40-F"} if annual else {"10-Q", "10-K", "20-F", "40-F"}
    candidates = [
        item
        for item in items
        if item.get("val") is not None and item.get("end") and item.get("form") in forms
    ]
    if not candidates and annual:
        return _latest_item(concept, annual=False)
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (str(item.get("end", "")), str(item.get("filed", ""))),
        reverse=True,
    )[0]


def _pick_fact(company_facts: dict[str, Any], tags: list[str], annual: bool = True) -> tuple[float | None, dict[str, Any] | None]:
    us_gaap = _facts(company_facts)
    for tag in tags:
        concept = us_gaap.get(tag)
        if not concept:
            continue
        item = _latest_item(concept, annual=annual)
        if item is not None:
            return float(item["val"]), {
                "tag": tag,
                "label": concept.get("label") or tag,
                "form": item.get("form"),
                "fy": item.get("fy"),
                "fp": item.get("fp"),
                "end": item.get("end"),
                "filed": item.get("filed"),
            }
    return None, None


def _sum_distinct(company_facts: dict[str, Any], tags: list[str]) -> tuple[float | None, list[dict[str, Any]]]:
    total = 0.0
    fields = []
    for tag in tags:
        value, field = _pick_fact(company_facts, [tag])
        if value is not None and field:
            total += value
            fields.append(field)
    if not fields:
        return None, []
    return total, fields


def _extract_interest_bearing_debt(
    company_facts: dict[str, Any],
    include_finance_leases: bool,
) -> tuple[float | None, list[dict[str, Any]]]:
    current, current_field = _pick_fact(company_facts, CURRENT_DEBT_TAGS)
    noncurrent, noncurrent_field = _pick_fact(company_facts, NONCURRENT_DEBT_TAGS)
    lease_total, lease_fields = _sum_distinct(company_facts, LEASE_TAGS if include_finance_leases else [])

    fields = []
    total = 0.0
    if current is not None and current_field:
        total += current
        fields.append(current_field)
    if noncurrent is not None and noncurrent_field:
        total += noncurrent
        fields.append(noncurrent_field)
    if lease_total is not None:
        total += lease_total
        fields.extend(lease_fields)

    if fields:
        return total, fields
    return None, []


def extract_latest_financial_snapshot(
    company_facts: dict[str, Any] | None,
    yfinance_data: dict[str, Any] | None,
    include_finance_leases: bool = False,
    use_yfinance_financial_fallback: bool = True,
) -> FinancialSnapshot:
    company_facts = company_facts or {}
    yfinance_data = yfinance_data or {}
    sources = []
    source_fields: dict[str, Any] = {}

    market_cap = yfinance_data.get("market_cap")
    if market_cap is not None:
        sources.append("yfinance unofficial fallback")
        source_fields["market_cap"] = "yfinance marketCap or price * shares outstanding"

    debt, debt_fields = _extract_interest_bearing_debt(company_facts, include_finance_leases)
    cash, cash_field = _pick_fact(company_facts, CASH_TAGS)
    securities, securities_fields = _sum_distinct(company_facts, SECURITIES_TAGS)
    revenue, revenue_field = _pick_fact(company_facts, REVENUE_TAGS)
    non_perm, non_perm_field = _pick_fact(company_facts, NON_PERMISSIBLE_TAGS)

    if any([debt_fields, cash_field, securities_fields, revenue_field, non_perm_field]):
        sources.append("SEC EDGAR")
    if debt_fields:
        source_fields["total_interest_bearing_debt"] = debt_fields
    if cash_field:
        source_fields["cash_and_equivalents"] = cash_field
    if securities_fields:
        source_fields["marketable_securities"] = securities_fields
    if revenue_field:
        source_fields["total_revenue"] = revenue_field
    if non_perm_field:
        source_fields["non_permissible_income"] = non_perm_field

    yf_financials = yfinance_data.get("financials") or {}
    yf_fields = yf_financials.get("source_fields") or {}
    if use_yfinance_financial_fallback and yfinance_data.get("status") == "ok":
        fallback_used = False
        if debt is None and yf_financials.get("total_interest_bearing_debt") is not None:
            debt = float(yf_financials["total_interest_bearing_debt"])
            source_fields["total_interest_bearing_debt"] = {
                "source": "yfinance unofficial financial fallback",
                **(yf_fields.get("total_interest_bearing_debt") or {}),
            }
            fallback_used = True
        if cash is None and yf_financials.get("cash_and_equivalents") is not None:
            cash = float(yf_financials["cash_and_equivalents"])
            source_fields["cash_and_equivalents"] = {
                "source": "yfinance unofficial financial fallback",
                **(yf_fields.get("cash_and_equivalents") or {}),
            }
            fallback_used = True
        if securities is None and yf_financials.get("marketable_securities") is not None:
            securities = float(yf_financials["marketable_securities"])
            source_fields["marketable_securities"] = {
                "source": "yfinance unofficial financial fallback",
                **(yf_fields.get("marketable_securities") or {}),
            }
            fallback_used = True
        if (revenue is None or revenue <= 0) and yf_financials.get("total_revenue") is not None:
            revenue = float(yf_financials["total_revenue"])
            source_fields["total_revenue"] = {
                "source": "yfinance unofficial financial fallback",
                **(yf_fields.get("total_revenue") or {}),
            }
            fallback_used = True
        if non_perm is None and yf_financials.get("non_permissible_income") is not None:
            non_perm = float(yf_financials["non_permissible_income"])
            source_fields["non_permissible_income"] = {
                "source": "yfinance unofficial financial fallback",
                **(yf_fields.get("non_permissible_income") or {}),
            }
            fallback_used = True
        if fallback_used:
            sources.append("yfinance unofficial financial fallback")

    period_field = revenue_field or non_perm_field or cash_field or (debt_fields[0] if debt_fields else None)
    return FinancialSnapshot(
        market_cap=float(market_cap) if market_cap is not None else None,
        total_interest_bearing_debt=debt,
        cash_and_equivalents=cash,
        marketable_securities=securities,
        total_revenue=revenue,
        non_permissible_income=non_perm,
        fiscal_period=(period_field or {}).get("fp"),
        fiscal_year=(period_field or {}).get("fy"),
        source_fields=source_fields,
        source=sources or ["automatic source unavailable"],
        as_of_date=(period_field or {}).get("end") or datetime.now(UTC).date().isoformat(),
    )
