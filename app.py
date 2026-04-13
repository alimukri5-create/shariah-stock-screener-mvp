"""Streamlit app for a beginner-friendly Shariah stock screener MVP."""

import streamlit as st

from methodology import get_default_methodology
from screener import screen_stock
from data_fetcher import get_stock_data
from utils import (
    clean_ticker,
    format_number,
    format_percentage,
    get_status_label,
)


st.set_page_config(page_title="Shariah Stock Screener")


def show_ratio_table(ratio_results: list[dict]) -> None:
    """Display ratio checks in a small beginner-friendly table."""
    if not ratio_results:
        st.info("No financial ratio checks were available.")
        return

    table_rows = []
    for item in ratio_results:
        table_rows.append(
            {
                "Ratio": item["label"],
                "Value": format_percentage(item.get("value")),
                "Threshold": item["threshold_label"],
                "Result": get_status_label(item["status"]),
                "Note": item["note"],
            }
        )

    st.dataframe(table_rows, use_container_width=True, hide_index=True)


def show_result(result: dict) -> None:
    """Render the screener result on the page."""
    company = result["company"]
    methodology = result["methodology"]
    business = result["business_screen"]
    financial = result["financial_screen"]
    income = result["income_screen"]

    st.subheader("Result")

    col1, col2 = st.columns(2)
    col1.metric("Company", company["company_name"])
    col2.metric("Ticker", company["ticker"])

    st.write(f"**Methodology:** {methodology['name']}")
    st.write(methodology["description"])

    verdict = result["final_verdict"]
    if verdict == "Compliant":
        st.success(f"Final verdict: {verdict}")
    elif verdict == "Non-compliant":
        st.error(f"Final verdict: {verdict}")
    else:
        st.warning(f"Final verdict: {verdict}")

    st.subheader("Screen Checks")
    st.write(f"**Business activity screen:** {get_status_label(business['status'])}")
    st.write(business["note"])

    st.write(f"**Financial ratio screen:** {get_status_label(financial['status'])}")
    st.write(financial["note"])

    st.write(f"**Income generation screen:** {get_status_label(income['status'])}")
    st.write(income["note"])

    st.subheader("Ratio Values")
    show_ratio_table(financial["ratio_results"])

    st.subheader("Income Screen Details")
    st.write(f"**Threshold:** {income['threshold_label']}")
    st.write(
        {
            "Selected possible non-compliant income fact": (
                income["selected_non_core_income_fact"]["label"]
                if income.get("selected_non_core_income_fact")
                else "Not found"
            ),
            "Selected fact category": (
                income["selected_non_core_income_fact"].get("category", "Unknown")
                if income.get("selected_non_core_income_fact")
                else "Not found"
            ),
            "Selected fact value": format_number(
                income["selected_non_core_income_fact"]["value"]
                if income.get("selected_non_core_income_fact")
                else None
            ),
            "Revenue fact": (
                income["revenue_fact"]["label"]
                if income.get("revenue_fact")
                else "Not found"
            ),
            "Revenue value": format_number(
                income["revenue_fact"]["value"]
                if income.get("revenue_fact")
                else None
            ),
            "Possible non-compliant income / Revenue": format_percentage(
                income.get("non_core_income_ratio")
            ),
        }
    )
    if income.get("non_core_income_facts"):
        st.write("**Other SEC candidate facts found:**")
        for item in income["non_core_income_facts"]:
            st.write(
                f"- {item['label']} ({item['category']}): {format_number(item['value'])}"
            )

    st.subheader("Plain-English Explanation")
    st.write(result["plain_english_explanation"])

    st.subheader("Confidence And Limitations")
    for note in result["limitations"]:
        st.write(f"- {note}")

    st.info(
        "This tool applies a stated screening methodology to prototype financial data. "
        "It is not a fatwa, religious ruling, or substitute for qualified scholarly advice."
    )

    with st.expander("Raw Data Used"):
        st.write(
            {
                "Sector": company.get("sector") or "Not available",
                "Industry": company.get("industry") or "Not available",
                "Market cap": format_number(company.get("market_cap")),
                "Total debt": format_number(company.get("total_debt")),
                "Cash": format_number(company.get("cash")),
                "Total assets": format_number(company.get("total_assets")),
                "Current assets": format_number(company.get("current_assets")),
            }
        )


def main() -> None:
    """Build the Streamlit page."""
    st.title("Shariah Stock Screener MVP")
    st.write(
        "Enter a US stock ticker to run a simple, transparent methodology-based "
        "Shariah screening check."
    )

    ticker_input = st.text_input("Ticker symbol", placeholder="Example: AAPL")
    run_screening = st.button("Run Screening")

    st.caption(
        "Prototype data sources: Yahoo Finance and SEC EDGAR. Some fields may be missing "
        "or incomplete."
    )

    if run_screening:
        ticker = clean_ticker(ticker_input)
        if not ticker:
            st.error("Please enter a ticker symbol before clicking Run Screening.")
            return

        methodology = get_default_methodology()

        with st.spinner("Fetching stock data and running the screening..."):
            stock_data = get_stock_data(ticker)

        if stock_data["status"] != "ok":
            st.error(stock_data["message"])
            if stock_data.get("limitations"):
                st.write("Known limitations:")
                for note in stock_data["limitations"]:
                    st.write(f"- {note}")
            return

        result = screen_stock(stock_data, methodology)
        show_result(result)

    st.subheader("Important Note")
    st.write(
        "This app is designed for learning and prototype screening only. It uses simple "
        "rules and limited data, especially for business activity screening."
    )


if __name__ == "__main__":
    main()
