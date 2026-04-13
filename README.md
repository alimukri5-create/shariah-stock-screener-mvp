# Shariah Stock Screener MVP

This is a beginner-friendly Streamlit app that checks one stock ticker at a time using a simple and transparent Shariah screening methodology.

Important: this is a **methodology-based prototype tool**, not a fatwa or religious ruling.

## What the app does

- Lets you enter one US stock ticker
- Fetches basic company and financial data from Yahoo Finance
- Runs a simple business activity screen
- Runs simple financial ratio checks
- Shows a final result:
  - `Compliant`
  - `Non-compliant`
  - `Insufficient data`

## Important limitations

- This app uses **Yahoo Finance via `yfinance`** for prototype purposes.
- Yahoo Finance is convenient for beginners, but it is **not an official institutional data feed**.
- Some tickers may have missing, delayed, or incomplete fields.
- The business activity screen is only a **placeholder** based on sector and industry text.
- Detailed revenue-level screening is **not implemented yet**.
- This tool should not be treated as absolute religious certainty.

## Project files

- `app.py` = Streamlit user interface
- `data_fetcher.py` = gets stock data
- `screener.py` = runs the screening logic
- `methodology.py` = stores the screening rules and thresholds
- `utils.py` = helper functions
- `requirements.txt` = Python packages

## Local setup

### 1. Make sure Python is installed

You need Python 3.10 or newer.

To check:

```powershell
python --version
```

### 2. Open the project folder in your terminal

Example:

```powershell
cd "C:\Users\ali_m\OneDrive\Documents\New project"
```

### 3. Install the required packages

```powershell
pip install -r requirements.txt
```

### 4. Run the app

```powershell
streamlit run app.py
```

### 5. Open the local link

Streamlit will show a local web address in the terminal, usually:

```text
http://localhost:8501
```

Open that link in your browser.

## How to use the app

1. Enter a ticker like `AAPL`
2. Click `Run Screening`
3. Read the result sections:
   - methodology used
   - business activity screen
   - financial ratio screen
   - final verdict
   - limitations and disclaimer

## Example behavior

### Example 1: likely valid stock

If you enter `AAPL`, the app should:

- fetch Apple company data
- show the methodology used
- calculate available ratios
- return a final verdict based on the configured rules

### Example 2: invalid ticker

If you enter `NOTAREALSTOCK`, the app should:

- not crash
- show a clear error message
- explain that no usable stock data was returned

### Example 3: partial data

If a ticker is missing important fields, the app should:

- still show any data it could fetch
- mark unavailable checks clearly
- return `Insufficient data` when needed

## Deploying on Streamlit Cloud

### 1. Put this project in a GitHub repository

Your repo should include:

- `app.py`
- `requirements.txt`
- the other `.py` files

### 2. Go to Streamlit Community Cloud

Open:

[https://share.streamlit.io/](https://share.streamlit.io/)

### 3. Connect your GitHub repo

Choose:

- your repository
- branch
- main file: `app.py`

### 4. Deploy

Streamlit Cloud will install the packages from `requirements.txt` and run the app.

## Notes about the current methodology

The MVP includes:

- a simple business activity screen using sector and industry keywords
- financial thresholds stored in `methodology.py`

The thresholds are easy to edit later in one place.

## Next improvements after MVP

- Add better business activity screening with segment revenue data
- Add a more robust and scholarly configurable methodology
- Add support for more exchanges and regions
- Add a history of previous screenings
- Add downloadable reports
- Add unit tests
- Replace Yahoo Finance with a stronger data provider
