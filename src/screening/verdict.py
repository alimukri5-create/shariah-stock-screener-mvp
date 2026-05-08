"""Verdict aggregation."""

from __future__ import annotations

from src.models import Confidence, CompanyProfile, RuleStatus, ScreeningRuleResult, ScreeningVerdict


def aggregate_verdict(
    profile: CompanyProfile,
    rule_results: list[ScreeningRuleResult],
    warnings: list[str] | None = None,
) -> ScreeningVerdict:
    warnings = warnings or []
    if any(result.status == RuleStatus.FAIL for result in rule_results):
        verdict = RuleStatus.FAIL
    elif any(result.status == RuleStatus.REVIEW_NEEDED for result in rule_results):
        verdict = RuleStatus.REVIEW_NEEDED
    else:
        verdict = RuleStatus.PASS

    missing_data = sorted({field for result in rule_results for field in result.missing_fields})
    data_sources = sorted({source for result in rule_results for source in result.source} | set(profile.source))

    if verdict == RuleStatus.REVIEW_NEEDED or missing_data:
        confidence = Confidence.LOW
    elif any(result.confidence == Confidence.MEDIUM for result in rule_results):
        confidence = Confidence.MEDIUM
    elif data_sources and all("SEC" in source for source in data_sources):
        confidence = Confidence.HIGH
    else:
        confidence = Confidence.MEDIUM

    company = profile.company_name or profile.ticker
    if verdict == RuleStatus.FAIL:
        summary = f"{company} fails the screen because at least one required Shariah rule failed."
    elif verdict == RuleStatus.REVIEW_NEEDED:
        summary = f"{company} needs review because the available automatic evidence is incomplete or ambiguous."
    else:
        summary = f"{company} passes all required automatic checks under the selected methodology."

    return ScreeningVerdict(
        ticker=profile.ticker,
        company_name=profile.company_name,
        verdict=verdict,
        confidence=confidence,
        one_sentence_summary=summary,
        rule_results=rule_results,
        data_sources=data_sources,
        missing_data=missing_data,
        warnings=warnings,
    )

