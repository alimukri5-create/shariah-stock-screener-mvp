"""AmanahScreen Streamlit application."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from src.config import APP_NAME, APP_TAGLINE
from src.data.cache import JsonCache
from src.data.etf_client import HALAL_ETFS, EtfHoldingsClient
from src.data.normalizer import extract_company_profile, extract_latest_financial_snapshot
from src.data.sec_client import SecClient
from src.data.yfinance_client import YFinanceClient
from src.models import CompanyProfile, Confidence, RuleStatus, ScreeningRuleResult, ScreeningStandard
from src.screening.portfolio import build_equal_weight_portfolio, combine_etf_holdings, sort_candidates
from src.screening.rules import screen_business_activity, screen_financial_ratios
from src.screening.standards import available_standards, get_standard
from src.screening.verdict import aggregate_verdict
from src.ui.components import blocker_card, rule_card, verdict_card
from src.ui.styles import CSS
from src.utils.formatting import clean_ticker


def unsupported_verdict(ticker: str, reason: str) -> Any:
    profile = CompanyProfile(ticker=ticker, company_name=ticker, source=["automatic source unavailable"])
    rule = ScreeningRuleResult(
        rule_id="automatic_coverage",
        rule_name="Automatic filing coverage",
        category="Coverage",
        status=RuleStatus.REVIEW_NEEDED,
        reason=reason,
        source=["SEC EDGAR"],
        missing_fields=["SEC CIK", "SEC filings"],
        confidence=Confidence.LOW,
    )
    return aggregate_verdict(profile, [rule], warnings=["Automatic SEC filing data is unavailable for this ticker or market."])


def screen_ticker(ticker: str, standard: ScreeningStandard, refresh: bool = False) -> Any:
    cache = JsonCache()
    sec = SecClient(cache)
    yf_client = YFinanceClient(cache)

    warnings = []
    yfinance_data = yf_client.get_profile(ticker, refresh=refresh)

    try:
        cik_result = sec.ticker_to_cik(ticker, refresh=refresh)
    except Exception as error:
        cik_result = None
        warnings.append(f"SEC ticker mapping unavailable: {error}")
    if not cik_result:
        if yfinance_data.get("status") == "ok":
            profile = extract_company_profile(ticker, None, None, yfinance_data)
            snapshot = extract_latest_financial_snapshot(
                None,
                yfinance_data,
                standard.include_finance_leases,
                standard.use_yfinance_financial_fallback,
            )
            rule_results = [screen_business_activity(profile, standard)]
            rule_results.extend(screen_financial_ratios(snapshot, standard))
            warnings.append("SEC filing coverage was unavailable, so the result cannot pass automatically.")
            return aggregate_verdict(profile, rule_results, warnings=warnings)
        return unsupported_verdict(
            ticker,
            "Review needed because SEC ticker-to-CIK mapping did not find this ticker and fallback market data was unavailable. Automatic filing data is unavailable for this market or symbol.",
        )

    submissions = None
    company_facts = None
    try:
        submissions = sec.get_company_submissions(cik_result["cik"], refresh=refresh)
    except Exception as error:
        warnings.append(f"SEC submissions unavailable: {error}")
    try:
        company_facts = sec.get_company_facts(cik_result["cik"], refresh=refresh)
    except Exception as error:
        warnings.append(f"SEC company facts unavailable: {error}")

    if yfinance_data.get("warning"):
        warnings.append(yfinance_data["warning"])
    if yfinance_data.get("status") == "error":
        warnings.append(f"yfinance fallback unavailable: {yfinance_data.get('error')}")
    profile = extract_company_profile(ticker, cik_result, submissions, yfinance_data)
    snapshot = extract_latest_financial_snapshot(
        company_facts,
        yfinance_data,
        standard.include_finance_leases,
        standard.use_yfinance_financial_fallback,
    )

    rule_results = [screen_business_activity(profile, standard)]
    rule_results.extend(screen_financial_ratios(snapshot, standard))
    return aggregate_verdict(profile, rule_results, warnings=warnings)


def sidebar_standard() -> ScreeningStandard:
    st.sidebar.header("Methodology")
    selected = st.sidebar.selectbox("Screening standard", available_standards())
    base = get_standard(selected)
    base.debt_threshold = st.sidebar.slider("Debt threshold", 0.0, 1.0, base.debt_threshold, 0.01)
    base.cash_securities_threshold = st.sidebar.slider(
        "Cash/securities threshold", 0.0, 1.0, base.cash_securities_threshold, 0.01
    )
    base.non_permissible_income_threshold = st.sidebar.slider(
        "Non-permissible income threshold", 0.0, 0.25, base.non_permissible_income_threshold, 0.005
    )
    base.conservative_mode = st.sidebar.toggle("Conservative mode", value=base.conservative_mode)
    base.include_finance_leases = st.sidebar.toggle("Include finance leases in debt", value=base.include_finance_leases)
    base.use_yfinance_financial_fallback = st.sidebar.toggle(
        "Use unofficial financial fallback",
        value=base.use_yfinance_financial_fallback,
        help="Uses yfinance statement rows for debt, cash, revenue, and interest income when SEC facts are missing.",
    )
    st.sidebar.header("Cache")
    st.sidebar.caption("Local JSON cache lives in data_cache/. Use refresh to bypass cached provider data.")
    st.sidebar.header("About")
    st.sidebar.caption(
        "AmanahScreen is automatic-only. Missing critical evidence leads to REVIEW NEEDED, not PASS."
    )
    return base


def parse_tickers(raw_value: str) -> list[str]:
    candidates = raw_value.replace(",", "\n").replace(" ", "\n").splitlines()
    tickers = []
    seen = set()
    for candidate in candidates:
        ticker = clean_ticker(candidate)
        if ticker and ticker not in seen:
            tickers.append(ticker)
            seen.add(ticker)
    return tickers[:50]


def first_failing_rule(verdict: Any) -> str:
    failed = next((result.rule_name for result in verdict.rule_results if result.status == RuleStatus.FAIL), "")
    return failed


def first_blocking_rule(verdict: Any) -> str:
    failed = next((result.rule_name for result in verdict.rule_results if result.status == RuleStatus.FAIL), None)
    review = next((result.rule_name for result in verdict.rule_results if result.status == RuleStatus.REVIEW_NEEDED), None)
    return failed or review or ""


def verdict_row(verdict: Any) -> dict[str, Any]:
    rule_statuses = {result.rule_id: result.status.value for result in verdict.rule_results}
    return {
        "ticker": verdict.ticker,
        "company": verdict.company_name or verdict.ticker,
        "verdict": verdict.verdict.value,
        "confidence": verdict.confidence.value,
        "missing_data_count": len(verdict.missing_data),
        "missing_data": ", ".join(verdict.missing_data),
        "failing_rule": first_failing_rule(verdict),
        "blocking_rule": first_blocking_rule(verdict),
        "business": rule_statuses.get("business_activity", ""),
        "debt": rule_statuses.get("debt_ratio", ""),
        "cash_securities": rule_statuses.get("cash_securities_ratio", ""),
        "non_permissible_income": rule_statuses.get("non_permissible_income_ratio", ""),
        "sources": ", ".join(verdict.data_sources),
        "summary": verdict.one_sentence_summary,
    }


def sort_watchlist(df: pd.DataFrame, sort_by: str) -> pd.DataFrame:
    verdict_order = {"PASS": 0, "REVIEW NEEDED": 1, "FAIL": 2}
    confidence_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_df = df.copy()
    if sort_by == "verdict":
        sorted_df["_sort"] = sorted_df["verdict"].map(verdict_order).fillna(9)
        return sorted_df.sort_values(["_sort", "ticker"]).drop(columns=["_sort"])
    if sort_by == "confidence":
        sorted_df["_sort"] = sorted_df["confidence"].map(confidence_order).fillna(9)
        return sorted_df.sort_values(["_sort", "ticker"]).drop(columns=["_sort"])
    if sort_by == "missing data":
        return sorted_df.sort_values(["missing_data_count", "ticker"], ascending=[False, True])
    if sort_by == "failing rule":
        return sorted_df.sort_values(["failing_rule", "ticker"], na_position="last")
    return sorted_df


def etf_candidate_row(base_row: dict[str, Any], verdict: Any, profile_data: dict[str, Any]) -> dict[str, Any]:
    row = verdict_row(verdict)
    sector = profile_data.get("sector") or "Unknown"
    return {
        **base_row,
        "company": row["company"],
        "verdict": row["verdict"],
        "confidence": row["confidence"],
        "sector": sector,
        "missing_data_count": row["missing_data_count"],
        "missing_data": row["missing_data"],
        "blocking_rule": row["blocking_rule"],
        "failing_rule": row["failing_rule"],
        "sources": row["sources"],
        "summary": row["summary"],
        "etfs": ", ".join(base_row.get("etfs", [])),
    }


def render_single_screen(standard: ScreeningStandard) -> None:
    col_input, col_button, col_refresh = st.columns([4, 1.2, 1.3])
    ticker = clean_ticker(col_input.text_input("Ticker", placeholder="AAPL"))
    screen_clicked = col_button.button("Screen Stock", use_container_width=True)
    refresh = col_refresh.button("Refresh Cache", use_container_width=True)

    if not ticker:
        st.info("Enter a stock ticker to screen it automatically.")
        return

    if screen_clicked or refresh:
        with st.spinner("Screening automatic evidence..."):
            try:
                st.session_state["single_verdict"] = screen_ticker(ticker, standard, refresh=refresh)
            except Exception as error:
                st.session_state["single_verdict"] = unsupported_verdict(
                    ticker,
                    f"Review needed because an automatic screening error occurred: {error}",
                )

    verdict = st.session_state.get("single_verdict")
    if not verdict:
        return

    verdict_card(verdict)
    blocker_card(verdict)
    st.subheader("Rule Summary")
    cols = st.columns(4)
    for index, result in enumerate(verdict.rule_results):
        with cols[index % 4]:
            rule_card(result)

    with st.expander("Why this verdict?", expanded=True):
        for result in verdict.rule_results:
            st.write(f"**{result.rule_name}: {result.status.value}.** {result.reason}")

    with st.expander("Source explanations"):
        for result in verdict.rule_results:
            st.write(f"**{result.rule_name}:** {result.source_detail or ', '.join(result.source)}")

    with st.expander("Data sources"):
        st.write(verdict.data_sources or ["Unavailable"])

    with st.expander("Missing data"):
        st.write(verdict.missing_data or ["No critical missing fields detected."])

    with st.expander("Methodology settings"):
        st.json(json.loads(standard.model_dump_json()))

    with st.expander("Developer diagnostics"):
        st.json(json.loads(verdict.model_dump_json()))


def render_watchlist(standard: ScreeningStandard) -> None:
    default_watchlist = "\n".join(st.session_state.get("saved_watchlist", ["AAPL", "MSFT", "BKSY", "SPIR", "SCZM"]))
    raw_watchlist = st.text_area(
        "Saved watchlist",
        value=default_watchlist,
        height=180,
        help="Enter 10-50 tickers separated by spaces, commas, or new lines.",
    )
    tickers = parse_tickers(raw_watchlist)
    st.caption(f"{len(tickers)} ticker(s) ready. The first 50 unique tickers will be screened.")

    col_save, col_screen, col_refresh, col_sort = st.columns([1.1, 1.2, 1.2, 1.8])
    save_clicked = col_save.button("Save Watchlist", use_container_width=True)
    screen_clicked = col_screen.button("Screen Watchlist", use_container_width=True)
    refresh = col_refresh.button("Refresh Batch", use_container_width=True)
    sort_by = col_sort.selectbox("Sort by", ["verdict", "confidence", "missing data", "failing rule"])

    if save_clicked:
        st.session_state["saved_watchlist"] = tickers
        st.success("Watchlist saved for this session.")

    if screen_clicked or refresh:
        if not tickers:
            st.warning("Add at least one ticker.")
            return
        results = []
        progress = st.progress(0)
        status = st.empty()
        for index, ticker in enumerate(tickers, start=1):
            status.write(f"Screening {ticker} ({index}/{len(tickers)})...")
            try:
                verdict = screen_ticker(ticker, standard, refresh=refresh)
            except Exception as error:
                verdict = unsupported_verdict(
                    ticker,
                    f"Review needed because an automatic screening error occurred: {error}",
                )
            results.append(verdict)
            progress.progress(index / len(tickers))
        status.empty()
        st.session_state["watchlist_results"] = results
        st.session_state["saved_watchlist"] = tickers

    results = st.session_state.get("watchlist_results", [])
    if not results:
        st.info("Screen the watchlist to see sortable verdicts and export a CSV.")
        return

    df = pd.DataFrame([verdict_row(verdict) for verdict in results])
    sorted_df = sort_watchlist(df, sort_by)
    st.dataframe(sorted_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download CSV",
        data=sorted_df.to_csv(index=False).encode("utf-8"),
        file_name="amanahscreen_watchlist.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_etf_portfolio(standard: ScreeningStandard) -> None:
    st.markdown(
        "Use halal ETF holdings as a discovery source, then let AmanahScreen re-screen the stocks. "
        "ETF inclusion is not treated as a Shariah verdict."
    )
    col_etfs, col_holdings, col_positions = st.columns([2.2, 1.2, 1.2])
    selected_etfs = col_etfs.multiselect(
        "Halal ETF references",
        options=list(HALAL_ETFS),
        default=["SPUS", "HLAL"],
        format_func=lambda ticker: f"{ticker} - {HALAL_ETFS[ticker]}",
    )
    holdings_limit = col_holdings.slider("Top holdings per ETF", 5, 30, 12, 1)
    max_positions = col_positions.slider("Draft positions", 5, 30, 15, 1)

    col_review, col_refresh, col_build = st.columns([1.8, 1.1, 1.4])
    include_review = col_review.toggle(
        "Include REVIEW NEEDED candidates",
        value=False,
        help="Keeps failing companies excluded, but allows research candidates into the draft portfolio.",
    )
    refresh = col_refresh.button("Refresh ETFs", use_container_width=True)
    build_clicked = col_build.button("Build Portfolio", use_container_width=True)

    if not selected_etfs:
        st.info("Choose at least one halal ETF reference.")
        return

    if build_clicked or refresh:
        cache = JsonCache()
        etf_client = EtfHoldingsClient(cache)
        yf_client = YFinanceClient(cache)
        with st.spinner("Pulling halal ETF holdings..."):
            payloads = [etf_client.get_holdings(etf, limit=holdings_limit, refresh=refresh) for etf in selected_etfs]

        coverage_rows = [
            {
                "etf": payload.get("etf"),
                "name": payload.get("name"),
                "status": payload.get("status"),
                "holdings_pulled": len(payload.get("holdings", [])),
                "source": payload.get("source"),
                "note": payload.get("note") or payload.get("warning") or payload.get("error") or "",
            }
            for payload in payloads
        ]
        combined = combine_etf_holdings(payloads)
        combined = combined[:50]

        screened_rows = []
        progress = st.progress(0)
        status = st.empty()
        for index, row in enumerate(combined, start=1):
            ticker = row["ticker"]
            status.write(f"Screening ETF holding {ticker} ({index}/{len(combined)})...")
            try:
                verdict = screen_ticker(ticker, standard, refresh=refresh)
            except Exception as error:
                verdict = unsupported_verdict(ticker, f"Review needed because an automatic screening error occurred: {error}")
            profile_data = yf_client.get_profile(ticker, refresh=False)
            screened_rows.append(etf_candidate_row(row, verdict, profile_data))
            progress.progress(index / max(len(combined), 1))
        status.empty()

        candidates = sort_candidates(screened_rows)
        portfolio = build_equal_weight_portfolio(candidates, max_positions=max_positions, include_review=include_review)
        st.session_state["etf_coverage_rows"] = coverage_rows
        st.session_state["etf_candidate_rows"] = candidates
        st.session_state["etf_portfolio_rows"] = portfolio

    coverage_rows = st.session_state.get("etf_coverage_rows", [])
    candidate_rows = st.session_state.get("etf_candidate_rows", [])
    portfolio_rows = st.session_state.get("etf_portfolio_rows", [])
    if not coverage_rows:
        st.info("Build a portfolio to pull ETF holdings, screen candidates, and export the results.")
        return

    st.subheader("ETF Coverage")
    st.dataframe(pd.DataFrame(coverage_rows), use_container_width=True, hide_index=True)

    st.subheader("Screened Candidates")
    candidate_df = pd.DataFrame(candidate_rows)
    display_columns = [
        "ticker",
        "company",
        "verdict",
        "confidence",
        "sector",
        "etf_count",
        "combined_etf_weight",
        "etfs",
        "blocking_rule",
        "missing_data_count",
    ]
    if not candidate_df.empty:
        st.dataframe(candidate_df[display_columns], use_container_width=True, hide_index=True)
        st.download_button(
            "Download Candidate CSV",
            data=candidate_df.to_csv(index=False).encode("utf-8"),
            file_name="amanahscreen_etf_candidates.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.subheader("Draft Equal-Weight Portfolio")
    if not portfolio_rows:
        st.warning("No eligible portfolio candidates were found under the current settings.")
        return
    portfolio_df = pd.DataFrame(portfolio_rows)
    portfolio_df["portfolio_weight"] = portfolio_df["portfolio_weight"].map(lambda value: f"{value:.1%}")
    portfolio_df["combined_etf_weight"] = portfolio_df["combined_etf_weight"].map(lambda value: f"{value:.1%}")
    portfolio_columns = [
        "ticker",
        "company",
        "portfolio_weight",
        "verdict",
        "confidence",
        "sector",
        "etfs",
        "combined_etf_weight",
        "blocking_rule",
    ]
    st.dataframe(portfolio_df[portfolio_columns], use_container_width=True, hide_index=True)
    st.download_button(
        "Download Portfolio CSV",
        data=portfolio_df.to_csv(index=False).encode("utf-8"),
        file_name="amanahscreen_etf_portfolio.csv",
        mime="text/csv",
        use_container_width=True,
    )
    with st.expander("How this portfolio draft works"):
        st.write(
            "The draft excludes FAIL results, ranks holdings by ETF overlap, verdict, ETF weight, and confidence, "
            "then assigns equal weights. REVIEW NEEDED names are included only when the toggle is on."
        )
        st.write(
            "This is a research workflow, not investment advice. ETF holdings come from yfinance, an unofficial fallback source."
        )


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="AS", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    standard = sidebar_standard()

    st.title(APP_NAME)
    st.markdown(f"<div class='amanah-tagline'>{APP_TAGLINE}</div>", unsafe_allow_html=True)

    single_tab, watchlist_tab, etf_tab = st.tabs(["Single Screen", "Watchlist", "ETF Portfolio"])
    with single_tab:
        render_single_screen(standard)
    with watchlist_tab:
        render_watchlist(standard)
    with etf_tab:
        render_etf_portfolio(standard)


if __name__ == "__main__":
    main()
