from tools.perplexity_client import search

RESEARCH_QUERY = """Analyze {ticker} stock for an investment decision. Provide the following data points:

1. Business model (2 sentences)
2. Revenue growth YoY (most recent quarter vs same quarter prior year): exact percentage
3. Gross margin (most recent quarter): exact percentage
4. Return on Equity (ROE) (trailing twelve months): exact percentage
5. Debt-to-Equity ratio: exact number
6. Free Cash Flow status: positive or negative, and approximate TTM amount in billions
7. P/E ratio and PEG ratio if available: exact numbers
8. Main competitive advantages (economic moat): 2-3 bullet points
9. Any significant negative developments in the past 30 days (lawsuits, guidance cuts, executive departures, etc.)

Be precise with numbers. If a metric is unavailable, state "N/A" rather than estimating.
"""


def build_dossier(ticker: str) -> dict:
    raw = search(RESEARCH_QUERY.format(ticker=ticker), max_tokens=800)
    return {"ticker": ticker, "raw_research": raw}


def build_dossiers(tickers: list[str]) -> list[dict]:
    dossiers = []
    for ticker in tickers:
        try:
            dossier = build_dossier(ticker)
            dossiers.append(dossier)
            print(f"  Researched {ticker}")
        except Exception as e:
            print(f"  Research failed for {ticker}: {e}")
    return dossiers
