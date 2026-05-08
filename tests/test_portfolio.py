from src.screening.portfolio import build_equal_weight_portfolio, combine_etf_holdings, sort_candidates


def test_combine_etf_holdings_counts_overlap_and_weight():
    payloads = [
        {
            "status": "ok",
            "etf": "SPUS",
            "holdings": [
                {"ticker": "AAPL", "company": "Apple Inc.", "holding_percent": 0.10},
                {"ticker": "MSFT", "company": "Microsoft", "holding_percent": 0.08},
            ],
        },
        {
            "status": "ok",
            "etf": "HLAL",
            "holdings": [{"ticker": "AAPL", "company": "Apple Inc.", "holding_percent": 0.12}],
        },
    ]
    rows = combine_etf_holdings(payloads)
    apple = next(row for row in rows if row["ticker"] == "AAPL")
    assert apple["etf_count"] == 2
    assert apple["combined_etf_weight"] == 0.22


def test_sort_candidates_prefers_etf_overlap_then_pass():
    rows = [
        {"ticker": "AAA", "etf_count": 1, "combined_etf_weight": 0.20, "verdict": "PASS", "confidence": "High"},
        {"ticker": "BBB", "etf_count": 2, "combined_etf_weight": 0.01, "verdict": "REVIEW NEEDED", "confidence": "Low"},
    ]
    assert sort_candidates(rows)[0]["ticker"] == "BBB"


def test_portfolio_excludes_fail_and_review_by_default():
    rows = [
        {"ticker": "PASS1", "etf_count": 1, "combined_etf_weight": 0.10, "verdict": "PASS", "confidence": "High"},
        {"ticker": "REV1", "etf_count": 2, "combined_etf_weight": 0.20, "verdict": "REVIEW NEEDED", "confidence": "Low"},
        {"ticker": "FAIL1", "etf_count": 3, "combined_etf_weight": 0.30, "verdict": "FAIL", "confidence": "Low"},
    ]
    portfolio = build_equal_weight_portfolio(rows, max_positions=10)
    assert [row["ticker"] for row in portfolio] == ["PASS1"]
    assert portfolio[0]["portfolio_weight"] == 1


def test_portfolio_can_include_review_research_candidates():
    rows = [
        {"ticker": "REV1", "etf_count": 2, "combined_etf_weight": 0.20, "verdict": "REVIEW NEEDED", "confidence": "Low"},
        {"ticker": "PASS1", "etf_count": 1, "combined_etf_weight": 0.10, "verdict": "PASS", "confidence": "High"},
    ]
    portfolio = build_equal_weight_portfolio(rows, max_positions=2, include_review=True)
    assert {row["ticker"] for row in portfolio} == {"REV1", "PASS1"}
    assert portfolio[0]["portfolio_weight"] == 0.5
