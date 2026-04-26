from tools.yfinance_client import fetch_fundamentals


def build_dossier(ticker: str) -> dict:
    """Fetch structured fundamentals for a single ticker via yfinance."""
    return fetch_fundamentals(ticker)


def build_dossiers(tickers: list[str]) -> list[dict]:
    """Fetch fundamentals for a list of tickers. Skips on error."""
    dossiers = []
    for ticker in tickers:
        try:
            dossier = build_dossier(ticker)
            dossiers.append(dossier)
            print(f"  Fetched {ticker} — {dossier.get('sector', 'unknown sector')}")
        except Exception as e:
            print(f"  Failed {ticker}: {e}")
    return dossiers
