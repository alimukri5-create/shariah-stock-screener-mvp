# AmanahScreen

AmanahScreen is a local-first Streamlit app that screens one stock ticker at a time and returns a simple Shariah-screening verdict:

- `PASS`
- `FAIL`
- `REVIEW NEEDED`

It is designed as a verdict engine for normal investors, not a financial-data dashboard.

## What It Does

- Screens US-listed public companies with SEC filing data.
- Uses SEC EDGAR APIs as the primary source.
- Uses yfinance only as an unofficial fallback for market cap and company profile fields.
- Can optionally use yfinance statement rows as an unofficial financial fallback when SEC facts are incomplete.
- Applies configurable AAOIFI-style thresholds by default.
- Explains every rule result, missing field, source, and confidence level.
- Shows raw ratio calculations such as debt divided by market capitalization.
- Screens a saved watchlist of up to 50 tickers with sortable results.
- Exports watchlist screening results to CSV.
- Pulls halal ETF top holdings as a discovery source and screens those candidates.
- Builds a simple equal-weight draft portfolio from screened ETF candidates.
- Returns `REVIEW NEEDED` when automatic evidence is incomplete.

## What It Does Not Do

- It does not provide a fatwa.
- It does not provide investment advice.
- It does not use OpenAI, LLMs, paid APIs, API keys, cloud databases, or user accounts.
- It does not allow manual market cap, debt, cash, revenue, interest income, or override inputs.
- It does not let users force `PASS` or `FAIL`.

## Why Automatic-Only

Manual financial inputs make a screening tool easy to misuse. AmanahScreen only uses automatic public data so every verdict is traceable to a source. If a critical value is missing or ambiguous, the app returns `REVIEW NEEDED` instead of inventing or assuming a number.

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

On macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Recommended SEC user agent:

```powershell
$env:SEC_USER_AGENT="AmanahScreen your-email@example.com"
```

## Deploy With GitHub And Streamlit Community Cloud

1. Push this folder to a GitHub repository.
2. Open Streamlit Community Cloud.
3. Create a new app from the repository.
4. Set the main file path to `app.py`.
5. Add `SEC_USER_AGENT` as an app secret or environment variable if available.

No paid data API keys are required.

## Data Sources

- SEC ticker-to-CIK mapping: `https://www.sec.gov/files/company_tickers.json`
- SEC submissions API: `https://data.sec.gov/submissions/CIK##########.json`
- SEC company facts API: `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
- yfinance unofficial fallback for market cap, sector, industry, and business summary.
- Optional yfinance unofficial financial fallback for debt, cash, revenue, and interest income when SEC facts are unavailable.
- yfinance unofficial ETF holdings fallback for halal ETF discovery lists.

## Screening Methodology

Default AAOIFI-style thresholds:

- Interest-bearing debt / market capitalization <= 30%
- Cash plus interest-bearing securities / market capitalization <= 30%
- Non-permissible income / total revenue <= 5%

The app also includes a configurable FTSE-style placeholder. Different Shariah standards vary, so the app exposes thresholds and conservative mode in the sidebar.

The sidebar also includes `Use unofficial financial fallback`. This can improve coverage for non-US or thin SEC filers, but results using it should be treated with lower confidence because yfinance is not an official filing source.

## ETF Portfolio Workflow

Use the `ETF Portfolio` tab to pull top holdings from halal ETF references such as `SPUS`, `HLAL`, `UMMA`, `SPRE`, and `SPSK`. AmanahScreen combines overlapping holdings, screens each stock, and creates a simple equal-weight draft portfolio.

Important behavior:

- ETF inclusion is used only as a discovery signal, not as a Shariah verdict.
- `FAIL` results are always excluded from the draft portfolio.
- `REVIEW NEEDED` candidates are excluded by default, but can be included as research candidates with the toggle.
- ETF holdings come from yfinance and are labelled as an unofficial fallback source.
- Candidate and portfolio tables can be exported to CSV.

## Why REVIEW NEEDED Is Not A Failure

`REVIEW NEEDED` means the app did not find enough automatic evidence to pass or fail the company. It is a conservative safety result, not a claim that the company is impermissible.

## Known Unsupported Cases

- Non-US tickers without SEC filing coverage.
- Companies without usable XBRL facts.
- Companies where market cap is unavailable from yfinance fallback.
- Companies where prohibited revenue is only available in segment notes or narrative filing text.
- Businesses with mixed activity that require human scholarly review.

## Limitations

- This app is not a fatwa.
- This app is not investment advice.
- Automatic screening depends on available public data.
- SEC coverage is strongest for US-listed companies.
- Segment-level prohibited revenue may not be available.
- yfinance is an unofficial fallback source.
- yfinance financial statement fallback can improve coverage, but it is not a substitute for full audited filing review.
- Halal ETF holdings can change and may not be exposed for every fund.
- A stock appearing in a halal ETF does not guarantee it passes every selected AmanahScreen rule.
- Missing data leads to `REVIEW NEEDED`, not `PASS`.
- Different Shariah boards may use different thresholds and interpretations.

## Testing

```powershell
pytest
```

## Important Files

- `app.py`: Streamlit app and orchestration.
- `src/screening/rules.py`: Pure Shariah screening rules.
- `src/screening/verdict.py`: Verdict aggregation.
- `src/data/sec_client.py`: SEC EDGAR client.
- `src/data/etf_client.py`: Halal ETF holdings discovery client.
- `src/data/normalizer.py`: SEC/yfinance normalization.
- `src/screening/portfolio.py`: ETF candidate ranking and equal-weight portfolio helper.
- `tests/`: Regression tests for rules, verdicts, cache, and normalization.

## Watchlist Workflow

Use the `Watchlist` tab to enter tickers separated by spaces, commas, or new lines. The app screens the first 50 unique tickers, then lets you sort by verdict, confidence, missing data, or failing rule. Use `Download CSV` to export the current sorted table.

## How To Extend Later

- Add more standards in `src/screening/standards.py`.
- Add stronger SIC and NAICS mappings to the business classifier.
- Add more XBRL concept mappings in `src/data/normalizer.py`.
- Add filing-note extraction only if it can be done without blocked scraping or paid APIs.
- Add exportable audit reports after the verdict model is stable.
