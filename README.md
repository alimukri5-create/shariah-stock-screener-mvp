# AmanahScreen

AmanahScreen is a Streamlit Shariah stock-screening app that returns one of three automatic verdicts:

- `PASS`
- `FAIL`
- `REVIEW NEEDED`

It is designed as a verdict engine for normal investors, not a financial-data dashboard.

## What It Does

- Screens one ticker at a time in the `Single Screen` tab.
- Screens up to 50 tickers in the `Watchlist` tab.
- Sorts watchlist results by verdict, confidence, missing data, or failing rule.
- Exports watchlist results to CSV.
- Shows raw ratio math, such as debt divided by market capitalization.
- Explains which data source was used for each rule.
- Uses SEC EDGAR as the primary source for US filing data.
- Uses yfinance as an unofficial fallback for market cap, profile fields, and optional statement rows.

## What It Does Not Do

- It is not a fatwa.
- It is not investment advice.
- It does not use OpenAI, LLMs, paid APIs, cloud databases, API keys, or user accounts.
- It does not allow manual debt, cash, revenue, market cap, or override inputs.
- It does not let users force `PASS` or `FAIL`.

## Methodology

Default AAOIFI-style thresholds:

- Interest-bearing debt / market capitalization <= 30%
- Cash plus interest-bearing securities / market capitalization <= 30%
- Non-permissible income / total revenue <= 5%

The sidebar lets users adjust thresholds, conservative mode, finance lease treatment, and the unofficial financial fallback.

## Data Sources

- SEC ticker-to-CIK mapping: `https://www.sec.gov/files/company_tickers.json`
- SEC submissions API: `https://data.sec.gov/submissions/CIK##########.json`
- SEC company facts API: `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
- yfinance unofficial fallback for market cap, profile data, and financial statement rows when enabled.

## Why REVIEW NEEDED Is Not A Failure

`REVIEW NEEDED` means the app did not find enough automatic evidence to pass or fail the company. Missing critical evidence never becomes `PASS`.

## Run Locally

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

macOS/Linux:

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

## Deploy On Streamlit Community Cloud

1. Open Streamlit Community Cloud.
2. Connect this GitHub repository.
3. Select branch `main`.
4. Set main file path to `app.py`.
5. Deploy.

No paid data API keys are required.

## Limitations

- SEC coverage is strongest for US-listed public companies.
- Segment-level prohibited revenue may not be available.
- yfinance is unofficial and may be incomplete or delayed.
- Different Shariah boards may use different thresholds and interpretations.
- Missing data leads to `REVIEW NEEDED`, not `PASS`.
