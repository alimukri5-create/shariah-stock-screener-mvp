"""Pure screening rules."""

from __future__ import annotations

import re

from src.models import (
    CompanyProfile,
    Confidence,
    FinancialSnapshot,
    RuleStatus,
    ScreeningRuleResult,
    ScreeningStandard,
)


PROHIBITED_STRONG_PHRASES = {
    "conventional banking": 6,
    "commercial bank": 6,
    "investment bank": 6,
    "credit card lending": 6,
    "payday lending": 6,
    "mortgage lending": 6,
    "consumer finance": 5,
    "casino operator": 7,
    "casino": 5,
    "gambling": 6,
    "sports betting": 6,
    "alcoholic beverages": 6,
    "tobacco": 6,
    "pork products": 6,
    "adult entertainment": 7,
    "weapons manufacturing": 7,
    "defense contractor": 5,
    "cannabis": 6,
    "recreational marijuana": 6,
    "insurance carrier": 6,
    "property and casualty insurance": 6,
    "life insurance": 6,
}

AMBIGUOUS_PHRASES = {
    "financial services": 3,
    "reit": 3,
    "real estate investment trust": 4,
    "financing": 2,
    "lending": 3,
    "brokerage": 2,
    "defense": 2,
    "aerospace and defense": 3,
}

PROHIBITED_SIC_PREFIXES = {
    "60": "conventional banking or credit institution SIC code",
    "61": "credit or lending SIC code",
    "62": "securities brokerage or dealer SIC code",
    "63": "insurance SIC code",
    "2082": "alcoholic beverages SIC code",
    "2111": "tobacco SIC code",
    "7990": "amusement/gambling-related SIC code",
}


def _text(profile: CompanyProfile) -> str:
    parts = [
        profile.sic_description,
        profile.sector,
        profile.industry,
        profile.description,
    ]
    return " ".join(part for part in parts if part).lower()


def _phrase_score(text: str, phrases: dict[str, int]) -> tuple[int, list[str]]:
    score = 0
    matches = []
    for phrase, weight in phrases.items():
        if re.search(rf"\b{re.escape(phrase)}\b", text):
            score += weight
            matches.append(phrase)
    return score, matches


def screen_business_activity(profile: CompanyProfile, standard: ScreeningStandard) -> ScreeningRuleResult:
    text = _text(profile)
    sources = profile.source or ["SEC EDGAR"]
    if not text and not profile.sic:
        return ScreeningRuleResult(
            rule_id="business_activity",
            rule_name="Business activity",
            category="Business",
            status=RuleStatus.REVIEW_NEEDED,
            reason="Business activity requires review because no SIC, sector, industry, or description was available from automatic sources.",
            source=sources,
            as_of_date=profile.as_of_date,
            missing_fields=["business description"],
            confidence=Confidence.LOW,
        )

    sic_reason = None
    if profile.sic:
        for prefix, reason in PROHIBITED_SIC_PREFIXES.items():
            if profile.sic.startswith(prefix):
                sic_reason = reason
                break

    strong_score, strong_matches = _phrase_score(text, PROHIBITED_STRONG_PHRASES)
    ambiguous_score, ambiguous_matches = _phrase_score(text, AMBIGUOUS_PHRASES)

    if sic_reason or strong_score >= 6:
        evidence = sic_reason or ", ".join(strong_matches)
        return ScreeningRuleResult(
            rule_id="business_activity",
            rule_name="Business activity",
            category="Business",
            status=RuleStatus.FAIL,
            reason=f"Business activity failed because automatic sources indicate core prohibited activity: {evidence}.",
            source=sources,
            as_of_date=profile.as_of_date,
            confidence=Confidence.HIGH if sic_reason else Confidence.MEDIUM,
        )

    review_cutoff = 3 if standard.conservative_mode else 5
    if ambiguous_score >= review_cutoff or strong_score > 0:
        matches = strong_matches + ambiguous_matches
        return ScreeningRuleResult(
            rule_id="business_activity",
            rule_name="Business activity",
            category="Business",
            status=RuleStatus.REVIEW_NEEDED,
            reason=(
                "Business activity requires review because the company description contains "
                f"potentially sensitive language ({', '.join(matches)}) without a clear prohibited revenue breakdown."
            ),
            source=sources,
            as_of_date=profile.as_of_date,
            missing_fields=["prohibited revenue breakdown"],
            confidence=Confidence.LOW,
        )

    return ScreeningRuleResult(
        rule_id="business_activity",
        rule_name="Business activity",
        category="Business",
        status=RuleStatus.PASS,
        reason="Business activity passed because no clear prohibited core activity was detected from available automatic sources.",
        source=sources,
        as_of_date=profile.as_of_date,
        confidence=Confidence.MEDIUM,
    )


def _ratio_rule(
    *,
    rule_id: str,
    rule_name: str,
    numerator_name: str,
    numerator: float | None,
    denominator_name: str,
    denominator: float | None,
    threshold: float,
    source: list[str],
    source_detail: str | None,
    as_of_date: str | None,
) -> ScreeningRuleResult:
    if denominator is None or denominator == 0:
        return ScreeningRuleResult(
            rule_id=rule_id,
            rule_name=rule_name,
            category="Financial",
            status=RuleStatus.REVIEW_NEEDED,
            threshold=threshold,
            numerator=numerator,
            denominator=denominator,
            reason=f"{rule_name} could not be calculated because {denominator_name} was unavailable or zero.",
            source_detail=source_detail,
            source=source,
            as_of_date=as_of_date,
            missing_fields=[denominator_name],
            confidence=Confidence.LOW,
        )
    if numerator is None:
        return ScreeningRuleResult(
            rule_id=rule_id,
            rule_name=rule_name,
            category="Financial",
            status=RuleStatus.REVIEW_NEEDED,
            threshold=threshold,
            denominator=denominator,
            reason=f"{rule_name} could not be calculated because {numerator_name} was unavailable from automatic filing data.",
            source_detail=source_detail,
            source=source,
            as_of_date=as_of_date,
            missing_fields=[numerator_name],
            confidence=Confidence.LOW,
        )

    observed = numerator / denominator
    status = RuleStatus.PASS if observed <= threshold else RuleStatus.FAIL
    direction = "passed" if status == RuleStatus.PASS else "failed"
    comparison = "below" if status == RuleStatus.PASS else "above"
    return ScreeningRuleResult(
        rule_id=rule_id,
        rule_name=rule_name,
        category="Financial",
        status=status,
        threshold=threshold,
        observed_value=observed,
        numerator=numerator,
        denominator=denominator,
        reason=f"{rule_name} {direction}: observed ratio was {observed:.1%}, {comparison} the {threshold:.1%} threshold.",
        source_detail=source_detail,
        source=source,
        as_of_date=as_of_date,
        confidence=Confidence.MEDIUM if any("yfinance" in s for s in source) else Confidence.HIGH,
    )


def _describe_field(field: object) -> str | None:
    if field is None:
        return None
    if isinstance(field, str):
        return field
    if isinstance(field, list):
        labels = [_describe_field(item) for item in field]
        return "; ".join(label for label in labels if label)
    if isinstance(field, dict):
        if field.get("source") == "yfinance unofficial financial fallback":
            label = field.get("label") or "statement row"
            period = field.get("period")
            return f"{label} from yfinance statements" + (f" ({period})" if period else "")
        label = field.get("label") or field.get("tag") or "SEC fact"
        form = field.get("form")
        fy = field.get("fy")
        suffix = " from SEC"
        if form:
            suffix += f" {form}"
        if fy:
            suffix += f" FY{fy}"
        return f"{label}{suffix}"
    return str(field)


def _source_detail(snapshot: FinancialSnapshot, rule_id: str) -> str | None:
    fields = snapshot.source_fields
    market_cap = _describe_field(fields.get("market_cap"))
    if rule_id == "debt_ratio":
        numerator = _describe_field(fields.get("total_interest_bearing_debt"))
        return "; ".join(part for part in [f"Debt: {numerator}" if numerator else None, f"Market cap: {market_cap}" if market_cap else None] if part)
    if rule_id == "cash_securities_ratio":
        cash = _describe_field(fields.get("cash_and_equivalents"))
        securities = _describe_field(fields.get("marketable_securities"))
        return "; ".join(part for part in [f"Cash: {cash}" if cash else None, f"Securities: {securities}" if securities else None, f"Market cap: {market_cap}" if market_cap else None] if part)
    if rule_id == "non_permissible_income_ratio":
        income = _describe_field(fields.get("non_permissible_income"))
        revenue = _describe_field(fields.get("total_revenue"))
        return "; ".join(part for part in [f"Interest/non-permissible income: {income}" if income else None, f"Revenue: {revenue}" if revenue else None] if part)
    return None


def screen_financial_ratios(snapshot: FinancialSnapshot, standard: ScreeningStandard) -> list[ScreeningRuleResult]:
    source = snapshot.source or ["SEC EDGAR"]
    cash_total = None
    if snapshot.cash_and_equivalents is not None or snapshot.marketable_securities is not None:
        cash_total = (snapshot.cash_and_equivalents or 0) + (snapshot.marketable_securities or 0)

    return [
        _ratio_rule(
            rule_id="debt_ratio",
            rule_name="Debt ratio",
            numerator_name="interest-bearing debt",
            numerator=snapshot.total_interest_bearing_debt,
            denominator_name="market capitalization",
            denominator=snapshot.market_cap,
            threshold=standard.debt_threshold,
            source=source,
            source_detail=_source_detail(snapshot, "debt_ratio"),
            as_of_date=snapshot.as_of_date,
        ),
        _ratio_rule(
            rule_id="cash_securities_ratio",
            rule_name="Cash and securities ratio",
            numerator_name="cash and interest-bearing securities",
            numerator=cash_total,
            denominator_name="market capitalization",
            denominator=snapshot.market_cap,
            threshold=standard.cash_securities_threshold,
            source=source,
            source_detail=_source_detail(snapshot, "cash_securities_ratio"),
            as_of_date=snapshot.as_of_date,
        ),
        _ratio_rule(
            rule_id="non_permissible_income_ratio",
            rule_name="Non-permissible income ratio",
            numerator_name="non-permissible income",
            numerator=snapshot.non_permissible_income,
            denominator_name="total revenue",
            denominator=snapshot.total_revenue,
            threshold=standard.non_permissible_income_threshold,
            source=source,
            source_detail=_source_detail(snapshot, "non_permissible_income_ratio"),
            as_of_date=snapshot.as_of_date,
        ),
    ]
