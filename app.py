"""AmanahScreen: automatic Shariah stock screening Streamlit app."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import time
from typing import Any

import pandas as pd
import requests
import streamlit as st

APP_NAME = "AmanahScreen"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_UA = os.getenv("SEC_USER_AGENT", "AmanahScreen/1.0 contact@example.com")

DEBT_CURRENT = ["DebtCurrent", "ShortTermBorrowings", "ShortTermDebt", "CurrentPortionOfLongTermDebt", "LongTermDebtCurrent", "CommercialPaper"]
DEBT_NONCURRENT = ["LongTermDebt", "LongTermDebtNoncurrent", "NotesPayable"]
LEASES = ["FinanceLeaseLiability", "FinanceLeaseLiabilityCurrent", "FinanceLeaseLiabilityNoncurrent"]
CASH = ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash", "CashEquivalentsAtCarryingValue"]
SECURITIES = ["ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesCurrent", "DebtSecuritiesAvailableForSaleCurrent"]
REVENUE = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet", "SalesRevenueServicesNet"]
NON_PERM = ["InterestIncomeExpenseNonOperatingNet", "InterestIncomeExpenseNonoperatingNet", "InterestIncomeNonOperating", "InterestIncomeNonoperating", "InterestIncomeOther", "InterestIncomeShortTermInvestmentOther", "InvestmentIncomeInterest", "InvestmentIncomeInterestAndDividend", "InvestmentIncomeNet", "InterestAndDividendIncomeOperating", "InterestIncomeOperating", "InterestRevenueExpenseNet"]
PROHIBITED_SIC_PREFIXES = {"60": "banking", "61": "lending", "62": "securities brokerage", "63": "insurance", "2082": "alcohol", "2111": "tobacco"}
PROHIBITED_PHRASES = ["commercial bank", "investment bank", "credit card lending", "payday lending", "casino", "gambling", "sports betting", "alcoholic beverages", "tobacco", "adult entertainment", "weapons manufacturing", "cannabis"]
AMBIGUOUS_PHRASES = ["financial services", "reit", "real estate investment trust", "lending", "brokerage", "defense"]

st.set_page_config(page_title=APP_NAME, page_icon="AS", layout="wide")

CSS = """
<style>
.main .block-container{max-width:1080px;padding-top:2rem} h1,h2,h3{color:#111;letter-spacing:0}
.amanah-tagline{color:#5f6662;margin-top:-.8rem;margin-bottom:1.4rem}.verdict-card,.rule-card{border:1px solid #e7e7e7;border-radius:8px;background:white;box-shadow:0 10px 30px rgba(0,0,0,.04)}
.verdict-card{padding:1.35rem}.rule-card{padding:1rem;min-height:300px}.verdict-badge{display:inline-block;padding:.42rem .8rem;border-radius:999px;color:white;font-weight:800;font-size:.9rem;letter-spacing:.04em}
.badge-pass{background:#0f8f5f}.badge-fail{background:#111}.badge-review{background:#b7791f}.blocker-card{border:1px solid #e7e7e7;border-left:4px solid #0f8f5f;border-radius:8px;padding:1rem;background:#eef8f3;margin:1rem 0}
.rule-title{font-weight:800;margin:.35rem 0}.muted{color:#666;font-size:.92rem}.small-label{color:#666;font-size:.8rem;text-transform:uppercase;letter-spacing:.05em}.metric-line{margin:.35rem 0}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def money(v: float | None) -> str:
    if v is None:
        return "Unavailable"
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    return f"${v:,.0f}"


def pct(v: float | None) -> str:
    return "Unavailable" if v is None else f"{v:.1%}"


def clean_ticker(x: str) -> str:
    return "".join(ch for ch in x.upper().strip() if ch.isalnum() or ch in {".", "-"})


def badge_class(status: str) -> str:
    return "badge-pass" if status == "PASS" else "badge-fail" if status == "FAIL" else "badge-review"


def sec_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers.update({"User-Agent": SEC_UA, "Accept": "application/json", "Accept-Encoding": "gzip, deflate"})
    return s


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def sec_json(url: str) -> Any:
    last = None
    session = sec_session()
    for attempt in range(3):
        try:
            r = session.get(url, timeout=20)
            if r.status_code == 429:
                time.sleep(1 + attempt)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last = exc
            time.sleep(.5 + attempt)
    raise RuntimeError(last)


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def ticker_to_cik(ticker: str) -> dict[str, Any] | None:
    mapping = sec_json(SEC_TICKERS)
    for item in mapping.values():
        if str(item.get("ticker", "")).upper() == ticker.upper():
            return {"cik": str(item.get("cik_str")).zfill(10), "company_name": item.get("title")}
    return None


def latest_fact(concept: dict[str, Any], annual: bool = True) -> dict[str, Any] | None:
    items = concept.get("units", {}).get("USD", [])
    forms = {"10-K", "20-F", "40-F"} if annual else {"10-Q", "10-K", "20-F", "40-F"}
    rows = [i for i in items if i.get("val") is not None and i.get("end") and i.get("form") in forms]
    if not rows and annual:
        return latest_fact(concept, annual=False)
    if not rows:
        return None
    return sorted(rows, key=lambda i: (str(i.get("end", "")), str(i.get("filed", ""))), reverse=True)[0]


def pick_fact(facts: dict[str, Any] | None, tags: list[str]) -> tuple[float | None, dict[str, Any] | None]:
    us = (facts or {}).get("facts", {}).get("us-gaap", {})
    for tag in tags:
        concept = us.get(tag)
        if concept:
            item = latest_fact(concept)
            if item:
                return float(item["val"]), {"tag": tag, "label": concept.get("label") or tag, "form": item.get("form"), "fy": item.get("fy"), "fp": item.get("fp"), "end": item.get("end")}
    return None, None


def sum_facts(facts: dict[str, Any] | None, tags: list[str]) -> tuple[float | None, list[dict[str, Any]]]:
    total, fields = 0.0, []
    for tag in tags:
        value, field = pick_fact(facts, [tag])
        if value is not None and field:
            total += value
            fields.append(field)
    return (total, fields) if fields else (None, [])


def debt_value(facts: dict[str, Any] | None, include_leases: bool) -> tuple[float | None, list[dict[str, Any]]]:
    current, current_field = pick_fact(facts, DEBT_CURRENT)
    noncurrent, noncurrent_field = pick_fact(facts, DEBT_NONCURRENT)
    leases, lease_fields = sum_facts(facts, LEASES if include_leases else [])
    total, fields = 0.0, []
    for value, field in [(current, current_field), (noncurrent, noncurrent_field)]:
        if value is not None and field:
            total += value
            fields.append(field)
    if leases is not None:
        total += leases
        fields.extend(lease_fields)
    return (total, fields) if fields else (None, [])


def statement_value(df: Any, labels: list[str]) -> tuple[float | None, dict[str, str] | None]:
    try:
        if df is None or df.empty:
            return None, None
        for label in labels:
            if label in df.index:
                s = df.loc[label].dropna()
                if not s.empty:
                    date = s.index[0]
                    return float(s.iloc[0]), {"label": label, "period": str(date.date() if hasattr(date, "date") else date)}
    except Exception:
        return None, None
    return None, None


@st.cache_data(ttl=60 * 30, show_spinner=False)
def yf_profile(ticker: str) -> dict[str, Any]:
    try:
        for k in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
            os.environ.pop(k, None)
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        bs, inc = stock.balance_sheet, stock.income_stmt
    except Exception as exc:
        return {"status": "error", "error": str(exc), "source": "yfinance unofficial fallback"}
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    market_cap = info.get("marketCap") or (float(price) * float(shares) if price and shares else None)
    debt, debt_field = statement_value(bs, ["Total Debt", "Current Debt And Capital Lease Obligation", "Long Term Debt And Capital Lease Obligation"])
    cash, cash_field = statement_value(bs, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
    cash_sti, cash_sti_field = statement_value(bs, ["Cash Cash Equivalents And Short Term Investments"])
    securities = cash_sti - cash if cash is not None and cash_sti is not None and cash_sti >= cash else None
    revenue, revenue_field = statement_value(inc, ["Total Revenue", "Operating Revenue"])
    interest, interest_field = statement_value(inc, ["Interest Income", "Investment Income Interest", "Net Non Operating Interest Income Expense"])
    return {"status": "ok", "source": "yfinance unofficial fallback", "market_cap": market_cap, "sector": info.get("sector"), "industry": info.get("industry"), "description": info.get("longBusinessSummary"), "company_name": info.get("longName") or info.get("shortName"), "financials": {"total_interest_bearing_debt": debt, "cash_and_equivalents": cash, "marketable_securities": securities, "total_revenue": revenue, "non_permissible_income": interest, "source_fields": {"total_interest_bearing_debt": debt_field, "cash_and_equivalents": cash_field, "marketable_securities": cash_sti_field, "total_revenue": revenue_field, "non_permissible_income": interest_field}}}


def field_text(field: Any) -> str | None:
    if not field:
        return None
    if isinstance(field, list):
        return "; ".join(x for x in [field_text(f) for f in field] if x)
    if isinstance(field, dict):
        if field.get("source") == "yfinance unofficial financial fallback":
            return f"{field.get('label', 'statement row')} from yfinance statements" + (f" ({field.get('period')})" if field.get("period") else "")
        label = field.get("label") or field.get("tag") or "SEC fact"
        suffix = " from SEC" + (f" {field.get('form')}" if field.get("form") else "") + (f" FY{field.get('fy')}" if field.get("fy") else "")
        return f"{label}{suffix}"
    return str(field)


def normalize(ticker: str, cik: dict[str, Any] | None, submissions: dict[str, Any] | None, facts: dict[str, Any] | None, yf: dict[str, Any], include_leases: bool, yf_financial_fallback: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    profile_sources = []
    if submissions:
        profile_sources.append("SEC EDGAR")
    if yf.get("status") == "ok":
        profile_sources.append("yfinance unofficial fallback")
    profile = {"ticker": ticker, "company_name": (submissions or {}).get("name") or (cik or {}).get("company_name") or yf.get("company_name") or ticker, "sic": str((submissions or {}).get("sic") or ""), "sic_description": (submissions or {}).get("sicDescription"), "sector": yf.get("sector"), "industry": yf.get("industry"), "description": yf.get("description"), "source": profile_sources or ["automatic source unavailable"]}
    market_cap = yf.get("market_cap") if yf.get("status") == "ok" else None
    sources, fields = (["yfinance unofficial fallback"] if market_cap else []), {}
    if market_cap:
        fields["market_cap"] = "yfinance marketCap or price * shares outstanding"
    debt, debt_fields = debt_value(facts, include_leases)
    cash, cash_field = pick_fact(facts, CASH)
    securities, securities_fields = sum_facts(facts, SECURITIES)
    revenue, revenue_field = pick_fact(facts, REVENUE)
    non_perm, non_perm_field = pick_fact(facts, NON_PERM)
    if any([debt_fields, cash_field, securities_fields, revenue_field, non_perm_field]):
        sources.append("SEC EDGAR")
    if debt_fields: fields["debt"] = debt_fields
    if cash_field: fields["cash"] = cash_field
    if securities_fields: fields["securities"] = securities_fields
    if revenue_field: fields["revenue"] = revenue_field
    if non_perm_field: fields["non_perm"] = non_perm_field
    fin = yf.get("financials") or {}
    fin_fields = fin.get("source_fields") or {}
    if yf_financial_fallback and yf.get("status") == "ok":
        used = False
        for local_name, key in [("debt", "total_interest_bearing_debt"), ("cash", "cash_and_equivalents"), ("securities", "marketable_securities"), ("revenue", "total_revenue"), ("non_perm", "non_permissible_income")]:
            current = {"debt": debt, "cash": cash, "securities": securities, "revenue": revenue, "non_perm": non_perm}[local_name]
            if (current is None or (local_name == "revenue" and current <= 0)) and fin.get(key) is not None:
                if local_name == "debt": debt = float(fin[key])
                if local_name == "cash": cash = float(fin[key])
                if local_name == "securities": securities = float(fin[key])
                if local_name == "revenue": revenue = float(fin[key])
                if local_name == "non_perm": non_perm = float(fin[key])
                fields[local_name] = {"source": "yfinance unofficial financial fallback", **(fin_fields.get(key) or {})}
                used = True
        if used:
            sources.append("yfinance unofficial financial fallback")
    snapshot = {"market_cap": market_cap, "debt": debt, "cash": cash, "securities": securities, "revenue": revenue, "non_perm": non_perm, "source": sorted(set(sources)) or ["automatic source unavailable"], "fields": fields}
    return profile, snapshot


def business_rule(profile: dict[str, Any], conservative: bool) -> dict[str, Any]:
    text = " ".join(str(profile.get(k) or "") for k in ["sic_description", "sector", "industry", "description"]).lower()
    for prefix, label in PROHIBITED_SIC_PREFIXES.items():
        if profile.get("sic", "").startswith(prefix):
            return rule("business_activity", "Business activity", "Business", "FAIL", None, None, None, f"Business activity failed because SEC SIC indicates {label}.", profile["source"], None)
    if any(p in text for p in PROHIBITED_PHRASES):
        return rule("business_activity", "Business activity", "Business", "FAIL", None, None, None, "Business activity failed because company description contains strong prohibited-sector language.", profile["source"], None)
    if conservative and any(p in text for p in AMBIGUOUS_PHRASES):
        return rule("business_activity", "Business activity", "Business", "REVIEW NEEDED", None, None, None, "Business activity requires review because the description contains sensitive or ambiguous industry language.", profile["source"], None, ["prohibited revenue breakdown"])
    if not text and not profile.get("sic"):
        return rule("business_activity", "Business activity", "Business", "REVIEW NEEDED", None, None, None, "Business activity requires review because no profile description was available.", profile["source"], None, ["business description"])
    return rule("business_activity", "Business activity", "Business", "PASS", None, None, None, "Business activity passed because no clear prohibited core activity was detected from automatic sources.", profile["source"], None)


def rule(rule_id: str, name: str, category: str, status: str, threshold: float | None, numerator: float | None, denominator: float | None, reason: str, sources: list[str], source_detail: str | None, missing: list[str] | None = None) -> dict[str, Any]:
    observed = numerator / denominator if numerator is not None and denominator not in (None, 0) else None
    return {"rule_id": rule_id, "rule_name": name, "category": category, "status": status, "threshold": threshold, "observed": observed, "numerator": numerator, "denominator": denominator, "reason": reason, "source": sources, "source_detail": source_detail, "missing": missing or []}


def ratio_rule(rule_id: str, name: str, num_name: str, numerator: float | None, den_name: str, denominator: float | None, threshold: float, sources: list[str], source_detail: str | None) -> dict[str, Any]:
    if denominator is None or denominator == 0:
        return rule(rule_id, name, "Financial", "REVIEW NEEDED", threshold, numerator, denominator, f"{name} could not be calculated because {den_name} was unavailable or zero.", sources, source_detail, [den_name])
    if numerator is None:
        return rule(rule_id, name, "Financial", "REVIEW NEEDED", threshold, numerator, denominator, f"{name} could not be calculated because {num_name} was unavailable from automatic data.", sources, source_detail, [num_name])
    observed = numerator / denominator
    status = "PASS" if observed <= threshold else "FAIL"
    return rule(rule_id, name, "Financial", status, threshold, numerator, denominator, f"{name} {'passed' if status == 'PASS' else 'failed'}: observed ratio was {observed:.1%}, {'below' if status == 'PASS' else 'above'} the {threshold:.1%} threshold.", sources, source_detail)


def screen(ticker: str, settings: dict[str, Any]) -> dict[str, Any]:
    ticker = clean_ticker(ticker)
    yf = yf_profile(ticker)
    warnings, cik, submissions, facts = [], None, None, None
    try:
        cik = ticker_to_cik(ticker)
    except Exception as exc:
        warnings.append(f"SEC ticker mapping unavailable: {exc}")
    if cik:
        try: submissions = sec_json(SEC_SUBMISSIONS.format(cik=cik["cik"]))
        except Exception as exc: warnings.append(f"SEC submissions unavailable: {exc}")
        try: facts = sec_json(SEC_FACTS.format(cik=cik["cik"]))
        except Exception as exc: warnings.append(f"SEC company facts unavailable: {exc}")
    elif yf.get("status") != "ok":
        return {"ticker": ticker, "company_name": ticker, "verdict": "REVIEW NEEDED", "confidence": "Low", "summary": "Automatic coverage is unavailable for this ticker.", "rules": [rule("coverage", "Automatic coverage", "Coverage", "REVIEW NEEDED", None, None, None, "No SEC filing data or fallback market data was available.", ["automatic source unavailable"], None, ["SEC CIK", "market data"])], "sources": ["automatic source unavailable"], "missing": ["SEC CIK", "market data"], "warnings": warnings}
    profile, snap = normalize(ticker, cik, submissions, facts, yf, settings["include_leases"], settings["yf_financial_fallback"])
    cash_total = None if snap["cash"] is None and snap["securities"] is None else (snap["cash"] or 0) + (snap["securities"] or 0)
    fields = snap["fields"]
    rules = [business_rule(profile, settings["conservative"])]
    rules.append(ratio_rule("debt_ratio", "Debt ratio", "interest-bearing debt", snap["debt"], "market capitalization", snap["market_cap"], settings["debt_threshold"], snap["source"], "; ".join(x for x in [f"Debt: {field_text(fields.get('debt'))}" if fields.get("debt") else None, f"Market cap: {field_text(fields.get('market_cap'))}" if fields.get("market_cap") else None] if x)))
    rules.append(ratio_rule("cash_securities_ratio", "Cash and securities ratio", "cash and interest-bearing securities", cash_total, "market capitalization", snap["market_cap"], settings["cash_threshold"], snap["source"], "; ".join(x for x in [f"Cash: {field_text(fields.get('cash'))}" if fields.get("cash") else None, f"Securities: {field_text(fields.get('securities'))}" if fields.get("securities") else None, f"Market cap: {field_text(fields.get('market_cap'))}" if fields.get("market_cap") else None] if x)))
    rules.append(ratio_rule("non_permissible_income_ratio", "Non-permissible income ratio", "non-permissible income", snap["non_perm"], "total revenue", snap["revenue"], settings["income_threshold"], snap["source"], "; ".join(x for x in [f"Interest/non-permissible income: {field_text(fields.get('non_perm'))}" if fields.get("non_perm") else None, f"Revenue: {field_text(fields.get('revenue'))}" if fields.get("revenue") else None] if x)))
    verdict = "FAIL" if any(r["status"] == "FAIL" for r in rules) else "REVIEW NEEDED" if any(r["status"] == "REVIEW NEEDED" for r in rules) else "PASS"
    missing = sorted({m for r in rules for m in r["missing"]})
    sources = sorted({s for r in rules for s in r["source"]} | set(profile["source"]))
    confidence = "Low" if verdict == "REVIEW NEEDED" or missing else "Medium" if any("yfinance" in s for s in sources) else "High"
    company = profile["company_name"]
    summary = f"{company} fails the screen because at least one required Shariah rule failed." if verdict == "FAIL" else f"{company} needs review because the available automatic evidence is incomplete or ambiguous." if verdict == "REVIEW NEEDED" else f"{company} passes all required automatic checks under the selected methodology."
    return {"ticker": ticker, "company_name": company, "verdict": verdict, "confidence": confidence, "summary": summary, "rules": rules, "sources": sources, "missing": missing, "warnings": warnings, "generated_at": datetime.now(timezone.utc).isoformat()}


def settings() -> dict[str, Any]:
    st.sidebar.header("Methodology")
    standard = st.sidebar.selectbox("Screening standard", ["AAOIFI-style", "FTSE-style placeholder"])
    defaults = (0.30, 0.30, 0.05) if standard == "AAOIFI-style" else (0.33, 0.33, 0.05)
    return {"debt_threshold": st.sidebar.slider("Debt threshold", 0.0, 1.0, defaults[0], .01), "cash_threshold": st.sidebar.slider("Cash/securities threshold", 0.0, 1.0, defaults[1], .01), "income_threshold": st.sidebar.slider("Non-permissible income threshold", 0.0, .25, defaults[2], .005), "conservative": st.sidebar.toggle("Conservative mode", True), "include_leases": st.sidebar.toggle("Include finance leases in debt", False), "yf_financial_fallback": st.sidebar.toggle("Use unofficial financial fallback", True, help="Uses yfinance statement rows when SEC facts are missing.")}


def verdict_card(v: dict[str, Any]) -> None:
    st.markdown(f"""<div class="verdict-card"><span class="verdict-badge {badge_class(v['verdict'])}">{v['verdict']}</span><h2>{v['company_name']}</h2><p>{v['summary']}</p><div class="metric-line"><span class="small-label">Confidence</span><br><strong>{v['confidence']}</strong></div><div class="metric-line"><span class="small-label">Ticker</span><br><strong>{v['ticker']}</strong></div><div class="metric-line"><span class="small-label">Sources</span><br>{', '.join(v['sources']) or 'Unavailable'}</div></div>""", unsafe_allow_html=True)


def blocker(v: dict[str, Any]) -> None:
    bad = next((r for r in v["rules"] if r["status"] == "FAIL"), None) or next((r for r in v["rules"] if r["status"] == "REVIEW NEEDED"), None)
    title = "Why not PASS?" if v["verdict"] != "PASS" else "What cleared the screen?"
    text = bad["reason"] if bad else "No blocking rule was found under the selected methodology."
    st.markdown(f"<div class='blocker-card'><div class='small-label'>{title}</div><strong>{text}</strong></div>", unsafe_allow_html=True)


def rule_card(r: dict[str, Any]) -> None:
    calc = "Unavailable" if r["numerator"] is None or r["denominator"] in (None, 0) or r["observed"] is None else f"{money(r['numerator'])} / {money(r['denominator'])} = {pct(r['observed'])}"
    st.markdown(f"""<div class="rule-card"><span class="verdict-badge {badge_class(r['status'])}">{r['status']}</span><div class="rule-title">{r['rule_name']}</div><div class="muted">{r['reason']}</div><div class="metric-line"><span class="small-label">Observed</span><br>{pct(r['observed']) if r['observed'] is not None else 'Unavailable'}</div><div class="metric-line"><span class="small-label">Calculation</span><br>{calc if r['category']=='Financial' else 'Not applicable'}</div><div class="metric-line"><span class="small-label">Threshold</span><br>{pct(r['threshold']) if r['threshold'] is not None else 'Not applicable'}</div><div class="metric-line"><span class="small-label">Missing</span><br>{', '.join(r['missing']) if r['missing'] else 'None'}</div><div class="metric-line"><span class="small-label">Source detail</span><br>{r['source_detail'] or ', '.join(r['source'])}</div></div>""", unsafe_allow_html=True)


def parse_tickers(raw: str) -> list[str]:
    out, seen = [], set()
    for part in raw.replace(",", "\n").replace(" ", "\n").splitlines():
        t = clean_ticker(part)
        if t and t not in seen:
            out.append(t); seen.add(t)
    return out[:50]


def row(v: dict[str, Any]) -> dict[str, Any]:
    statuses = {r["rule_id"]: r["status"] for r in v["rules"]}
    fail = next((r["rule_name"] for r in v["rules"] if r["status"] == "FAIL"), "")
    block = fail or next((r["rule_name"] for r in v["rules"] if r["status"] == "REVIEW NEEDED"), "")
    return {"ticker": v["ticker"], "company": v["company_name"], "verdict": v["verdict"], "confidence": v["confidence"], "missing_data_count": len(v["missing"]), "missing_data": ", ".join(v["missing"]), "failing_rule": fail, "blocking_rule": block, "business": statuses.get("business_activity", ""), "debt": statuses.get("debt_ratio", ""), "cash_securities": statuses.get("cash_securities_ratio", ""), "non_permissible_income": statuses.get("non_permissible_income_ratio", ""), "sources": ", ".join(v["sources"]), "summary": v["summary"]}


def sort_df(df: pd.DataFrame, sort_by: str) -> pd.DataFrame:
    if sort_by == "verdict":
        return df.assign(_s=df["verdict"].map({"PASS": 0, "REVIEW NEEDED": 1, "FAIL": 2}).fillna(9)).sort_values(["_s", "ticker"]).drop(columns="_s")
    if sort_by == "confidence":
        return df.assign(_s=df["confidence"].map({"High": 0, "Medium": 1, "Low": 2}).fillna(9)).sort_values(["_s", "ticker"]).drop(columns="_s")
    if sort_by == "missing data":
        return df.sort_values(["missing_data_count", "ticker"], ascending=[False, True])
    return df.sort_values(["failing_rule", "ticker"], na_position="last")


def single_tab(cfg: dict[str, Any]) -> None:
    c1, c2, c3 = st.columns([4, 1.2, 1.3])
    ticker = clean_ticker(c1.text_input("Ticker", placeholder="AAPL"))
    go = c2.button("Screen Stock", use_container_width=True)
    refresh = c3.button("Refresh Cache", use_container_width=True)
    if refresh:
        st.cache_data.clear()
    if not ticker:
        st.info("Enter a stock ticker to screen it automatically.")
        return
    if go or refresh:
        with st.spinner("Screening automatic evidence..."):
            st.session_state["single"] = screen(ticker, cfg)
    v = st.session_state.get("single")
    if not v:
        return
    verdict_card(v); blocker(v)
    st.subheader("Rule Summary")
    cols = st.columns(4)
    for i, r in enumerate(v["rules"]):
        with cols[i % 4]: rule_card(r)
    with st.expander("Why this verdict?", expanded=True):
        for r in v["rules"]: st.write(f"**{r['rule_name']}: {r['status']}.** {r['reason']}")
    with st.expander("Source explanations"):
        for r in v["rules"]: st.write(f"**{r['rule_name']}:** {r['source_detail'] or ', '.join(r['source'])}")
    with st.expander("Missing data"): st.write(v["missing"] or ["No critical missing fields detected."])
    with st.expander("Developer diagnostics"): st.json(v)


def watchlist_tab(cfg: dict[str, Any]) -> None:
    raw = st.text_area("Saved watchlist", value="AAPL\nMSFT\nBKSY\nSPIR\nSCZM", height=180, help="Enter up to 50 tickers separated by spaces, commas, or new lines.")
    tickers = parse_tickers(raw)
    st.caption(f"{len(tickers)} ticker(s) ready. The first 50 unique tickers will be screened.")
    c1, c2, c3 = st.columns([1.2, 1.2, 1.8])
    go = c1.button("Screen Watchlist", use_container_width=True)
    refresh = c2.button("Refresh Batch", use_container_width=True)
    sort_by = c3.selectbox("Sort by", ["verdict", "confidence", "missing data", "failing rule"])
    if refresh:
        st.cache_data.clear()
    if go or refresh:
        rows, progress, status = [], st.progress(0), st.empty()
        for i, t in enumerate(tickers, start=1):
            status.write(f"Screening {t} ({i}/{len(tickers)})...")
            rows.append(screen(t, cfg)); progress.progress(i / max(len(tickers), 1))
        status.empty(); st.session_state["watchlist"] = rows
    results = st.session_state.get("watchlist", [])
    if not results:
        st.info("Screen the watchlist to see sortable verdicts and export a CSV.")
        return
    df = sort_df(pd.DataFrame([row(v) for v in results]), sort_by)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), "amanahscreen_watchlist.csv", "text/csv", use_container_width=True)


def main() -> None:
    cfg = settings()
    st.title(APP_NAME)
    st.markdown("<div class='amanah-tagline'>Automatic Shariah screening for SEC-reporting stocks.</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["Single Screen", "Watchlist"])
    with tab1: single_tab(cfg)
    with tab2: watchlist_tab(cfg)
    st.caption("Not a fatwa. Not investment advice. Missing critical evidence leads to REVIEW NEEDED, not PASS.")


if __name__ == "__main__":
    main()
