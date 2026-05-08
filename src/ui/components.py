"""Reusable Streamlit components."""

from __future__ import annotations

import streamlit as st

from src.models import RuleStatus, ScreeningRuleResult, ScreeningVerdict
from src.utils.formatting import money, percent


def _badge_class(status: RuleStatus) -> str:
    if status == RuleStatus.PASS:
        return "badge-pass"
    if status == RuleStatus.FAIL:
        return "badge-fail"
    return "badge-review"


def verdict_card(verdict: ScreeningVerdict) -> None:
    st.markdown(
        f"""
        <div class="verdict-card">
          <span class="verdict-badge {_badge_class(verdict.verdict)}">{verdict.verdict.value}</span>
          <h2>{verdict.company_name or verdict.ticker}</h2>
          <p>{verdict.one_sentence_summary}</p>
          <div class="metric-line"><span class="small-label">Confidence</span><br><strong>{verdict.confidence.value}</strong></div>
          <div class="metric-line"><span class="small-label">Ticker</span><br><strong>{verdict.ticker}</strong></div>
          <div class="metric-line"><span class="small-label">Sources</span><br>{", ".join(verdict.data_sources) or "Unavailable"}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def blocker_text(verdict: ScreeningVerdict) -> str:
    if verdict.verdict == RuleStatus.FAIL:
        failed = next((result for result in verdict.rule_results if result.status == RuleStatus.FAIL), None)
        return failed.reason if failed else "At least one required rule failed."
    if verdict.verdict == RuleStatus.REVIEW_NEEDED:
        review = next((result for result in verdict.rule_results if result.status == RuleStatus.REVIEW_NEEDED), None)
        return review.reason if review else "Critical automatic evidence was missing."
    return "No blocking rule was found under the selected methodology."


def blocker_card(verdict: ScreeningVerdict) -> None:
    title = "Why not PASS?" if verdict.verdict != RuleStatus.PASS else "What cleared the screen?"
    st.markdown(
        f"""
        <div class="blocker-card">
          <div class="small-label">{title}</div>
          <strong>{blocker_text(verdict)}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


def calculation_text(result: ScreeningRuleResult) -> str:
    if result.numerator is None or result.denominator is None or result.observed_value is None:
        return "Unavailable"
    return f"{money(result.numerator)} / {money(result.denominator)} = {percent(result.observed_value)}"


def rule_card(result: ScreeningRuleResult) -> None:
    observed = percent(result.observed_value) if result.observed_value is not None else "Unavailable"
    threshold = percent(result.threshold) if result.threshold is not None else "Not applicable"
    missing = ", ".join(result.missing_fields) if result.missing_fields else "None"
    calculation = calculation_text(result) if result.category == "Financial" else "Not applicable"
    source_detail = result.source_detail or ", ".join(result.source)
    st.markdown(
        f"""
        <div class="rule-card">
          <span class="verdict-badge {_badge_class(result.status)}">{result.status.value}</span>
          <div class="rule-title">{result.rule_name}</div>
          <div class="muted">{result.reason}</div>
          <div class="metric-line"><span class="small-label">Observed</span><br>{observed}</div>
          <div class="metric-line"><span class="small-label">Calculation</span><br>{calculation}</div>
          <div class="metric-line"><span class="small-label">Threshold</span><br>{threshold}</div>
          <div class="metric-line"><span class="small-label">Missing</span><br>{missing}</div>
          <div class="metric-line"><span class="small-label">Source detail</span><br>{source_detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
