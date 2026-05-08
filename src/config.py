"""Application configuration."""

from __future__ import annotations

from pathlib import Path


APP_NAME = "AmanahScreen"
APP_TAGLINE = "Automatic Shariah screening for SEC-reporting stocks."
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / "data_cache"
DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 12
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
DEFAULT_SEC_USER_AGENT = "AmanahScreen/1.0 contact@example.com"

