from src.models import CompanyProfile, Confidence, RuleStatus, ScreeningRuleResult
from src.screening.verdict import aggregate_verdict


def rule(status: RuleStatus) -> ScreeningRuleResult:
    return ScreeningRuleResult(
        rule_id="x",
        rule_name="Rule",
        category="Test",
        status=status,
        reason="Test reason.",
        source=["SEC EDGAR"],
        confidence=Confidence.HIGH,
    )


def test_pass_when_all_rules_pass():
    verdict = aggregate_verdict(CompanyProfile(ticker="AAPL"), [rule(RuleStatus.PASS)])
    assert verdict.verdict == RuleStatus.PASS


def test_fail_when_any_rule_fails():
    verdict = aggregate_verdict(
        CompanyProfile(ticker="AAPL"),
        [rule(RuleStatus.PASS), rule(RuleStatus.FAIL), rule(RuleStatus.REVIEW_NEEDED)],
    )
    assert verdict.verdict == RuleStatus.FAIL


def test_review_when_no_fail_but_review_needed():
    verdict = aggregate_verdict(
        CompanyProfile(ticker="AAPL"),
        [rule(RuleStatus.PASS), rule(RuleStatus.REVIEW_NEEDED)],
    )
    assert verdict.verdict == RuleStatus.REVIEW_NEEDED
    assert verdict.confidence == Confidence.LOW

