from src.models import CompanyProfile, FinancialSnapshot, RuleStatus, ScreeningStandard
from src.screening.rules import screen_business_activity, screen_financial_ratios


def test_debt_ratio_boundary_passes_at_threshold():
    standard = ScreeningStandard(name="AAOIFI-style", debt_threshold=0.30)
    snapshot = FinancialSnapshot(
        market_cap=100,
        total_interest_bearing_debt=30,
        cash_and_equivalents=1,
        marketable_securities=1,
        total_revenue=100,
        non_permissible_income=1,
        source=["SEC EDGAR"],
    )
    result = screen_financial_ratios(snapshot, standard)[0]
    assert result.status == RuleStatus.PASS
    assert result.observed_value == 0.30


def test_debt_ratio_fails_above_threshold():
    standard = ScreeningStandard(name="AAOIFI-style", debt_threshold=0.30)
    snapshot = FinancialSnapshot(market_cap=100, total_interest_bearing_debt=31, source=["SEC EDGAR"])
    assert screen_financial_ratios(snapshot, standard)[0].status == RuleStatus.FAIL


def test_missing_denominator_reviews():
    standard = ScreeningStandard(name="AAOIFI-style")
    snapshot = FinancialSnapshot(total_interest_bearing_debt=10, source=["SEC EDGAR"])
    result = screen_financial_ratios(snapshot, standard)[0]
    assert result.status == RuleStatus.REVIEW_NEEDED
    assert "market capitalization" in result.missing_fields


def test_missing_numerator_reviews():
    standard = ScreeningStandard(name="AAOIFI-style")
    snapshot = FinancialSnapshot(market_cap=100, source=["SEC EDGAR"])
    result = screen_financial_ratios(snapshot, standard)[0]
    assert result.status == RuleStatus.REVIEW_NEEDED
    assert "interest-bearing debt" in result.missing_fields


def test_cash_securities_ratio_calculates():
    standard = ScreeningStandard(name="AAOIFI-style", cash_securities_threshold=0.30)
    snapshot = FinancialSnapshot(
        market_cap=100,
        total_interest_bearing_debt=1,
        cash_and_equivalents=20,
        marketable_securities=5,
        total_revenue=100,
        non_permissible_income=1,
        source=["SEC EDGAR"],
    )
    assert screen_financial_ratios(snapshot, standard)[1].observed_value == 0.25


def test_non_permissible_income_ratio_missing_is_review():
    standard = ScreeningStandard(name="AAOIFI-style")
    snapshot = FinancialSnapshot(market_cap=100, total_revenue=100, source=["SEC EDGAR"])
    assert screen_financial_ratios(snapshot, standard)[2].status == RuleStatus.REVIEW_NEEDED


def test_business_strong_phrase_fails():
    profile = CompanyProfile(ticker="BANK", description="The company is a commercial bank.")
    assert screen_business_activity(profile, ScreeningStandard(name="AAOIFI-style")).status == RuleStatus.FAIL


def test_business_weak_bank_context_does_not_fail():
    profile = CompanyProfile(ticker="FOOD", description="The company supports food bank donation programs.")
    assert screen_business_activity(profile, ScreeningStandard(name="AAOIFI-style")).status == RuleStatus.PASS


def test_conservative_mode_reviews_ambiguous_financial_services():
    profile = CompanyProfile(ticker="FIN", description="The company provides financial services software.")
    result = screen_business_activity(profile, ScreeningStandard(name="AAOIFI-style", conservative_mode=True))
    assert result.status == RuleStatus.REVIEW_NEEDED

