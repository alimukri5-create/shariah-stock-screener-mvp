from src.data.normalizer import extract_company_profile, extract_latest_financial_snapshot


def test_normalizer_handles_incomplete_sec_facts():
    profile = extract_company_profile(
        "AAPL",
        {"cik": "0000320193", "company_name": "Apple Inc."},
        {"name": "Apple Inc.", "sic": "3571", "sicDescription": "Electronic Computers"},
        {"status": "ok", "sector": "Technology", "industry": "Consumer Electronics"},
    )
    snapshot = extract_latest_financial_snapshot({}, {"status": "ok", "market_cap": 1000})
    assert profile.company_name == "Apple Inc."
    assert snapshot.market_cap == 1000
    assert snapshot.total_revenue is None


def test_normalizer_extracts_latest_revenue_fact():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenue",
                    "units": {
                        "USD": [
                            {"val": 10, "end": "2022-12-31", "filed": "2023-01-30", "form": "10-K", "fy": 2022, "fp": "FY"},
                            {"val": 15, "end": "2023-12-31", "filed": "2024-01-30", "form": "10-K", "fy": 2023, "fp": "FY"},
                        ]
                    },
                }
            }
        }
    }
    snapshot = extract_latest_financial_snapshot(facts, {})
    assert snapshot.total_revenue == 15
    assert snapshot.fiscal_year == 2023


def test_normalizer_extracts_common_interest_income_variant():
    facts = {
        "facts": {
            "us-gaap": {
                "InvestmentIncomeInterestAndDividend": {
                    "label": "Interest and dividend income",
                    "units": {
                        "USD": [
                            {"val": 4, "end": "2023-12-31", "filed": "2024-01-30", "form": "10-K", "fy": 2023, "fp": "FY"}
                        ]
                    },
                }
            }
        }
    }
    snapshot = extract_latest_financial_snapshot(facts, {})
    assert snapshot.non_permissible_income == 4
    assert snapshot.source_fields["non_permissible_income"]["tag"] == "InvestmentIncomeInterestAndDividend"


def test_normalizer_uses_yfinance_financial_fallback_when_sec_missing():
    yfinance_data = {
        "status": "ok",
        "market_cap": 1000,
        "financials": {
            "total_interest_bearing_debt": 100,
            "cash_and_equivalents": 50,
            "marketable_securities": 25,
            "total_revenue": 500,
            "non_permissible_income": 10,
            "source_fields": {
                "total_revenue": {"label": "Total Revenue", "period": "2025-12-31"},
            },
        },
    }
    snapshot = extract_latest_financial_snapshot({}, yfinance_data)
    assert snapshot.total_interest_bearing_debt == 100
    assert snapshot.total_revenue == 500
    assert "yfinance unofficial financial fallback" in snapshot.source


def test_normalizer_uses_fallback_when_sec_revenue_is_zero():
    facts = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "units": {
                        "USD": [
                            {"val": 0, "end": "2020-12-31", "filed": "2021-03-30", "form": "10-K", "fy": 2020, "fp": "FY"}
                        ]
                    },
                }
            }
        }
    }
    yfinance_data = {
        "status": "ok",
        "financials": {
            "total_revenue": 100,
            "source_fields": {"total_revenue": {"label": "Total Revenue", "period": "2025-12-31"}},
        },
    }
    snapshot = extract_latest_financial_snapshot(facts, yfinance_data)
    assert snapshot.total_revenue == 100
    assert snapshot.source_fields["total_revenue"]["source"] == "yfinance unofficial financial fallback"


def test_normalizer_does_not_double_count_overlapping_debt_tags():
    facts = {
        "facts": {
            "us-gaap": {
                "DebtCurrent": {
                    "label": "Debt, Current",
                    "units": {"USD": [{"val": 8, "end": "2025-12-31", "filed": "2026-03-01", "form": "10-K", "fy": 2025, "fp": "FY"}]},
                },
                "LongTermDebt": {
                    "label": "Long-term Debt",
                    "units": {"USD": [{"val": 200, "end": "2025-12-31", "filed": "2026-03-01", "form": "10-K", "fy": 2025, "fp": "FY"}]},
                },
                "LongTermDebtNoncurrent": {
                    "label": "Long-term Debt, Noncurrent",
                    "units": {"USD": [{"val": 192, "end": "2025-12-31", "filed": "2026-03-01", "form": "10-K", "fy": 2025, "fp": "FY"}]},
                },
            }
        }
    }
    snapshot = extract_latest_financial_snapshot(facts, {})
    assert snapshot.total_interest_bearing_debt == 208
