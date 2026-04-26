import os
import requests

# Zoya Finance API — https://zoya.finance
# If the API key is absent or the endpoint returns an error, compliance
# falls back to "not_found" so Claude can do a secondary check.
ZOYA_BASE_URL = "https://api.zoya.finance"


def check_compliance(ticker: str) -> str:
    """
    Returns one of: 'compliant', 'non_compliant', 'borderline', 'not_found'

    'not_found' means Zoya has no data — Claude will do secondary screening.
    """
    api_key = os.getenv("ZOYA_API_KEY")
    if not api_key:
        return "not_found"

    try:
        resp = requests.get(
            f"{ZOYA_BASE_URL}/v1/stocks/{ticker}/compliance",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 404:
            return "not_found"
        resp.raise_for_status()

        data = resp.json()
        status = data.get("compliance_status", "").lower()

        if "non_compliant" in status or "not_compliant" in status:
            return "non_compliant"
        if "doubtful" in status or "borderline" in status or "questionable" in status:
            return "borderline"
        if "compliant" in status:
            return "compliant"
        return "not_found"

    except requests.RequestException:
        return "not_found"


def batch_check(tickers: list[str]) -> dict[str, str]:
    """Check a list of tickers. Returns dict of ticker → status."""
    return {ticker: check_compliance(ticker) for ticker in tickers}
