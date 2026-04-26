"""
Claude-based sharia compliance screener.

Screens tickers in bulk using Claude's knowledge of company business models,
applying AAOIFI criteria. The Analyst agent performs a deeper check on
research candidates once full Perplexity dossiers are available.
"""
import json
from tools.claude_client import complete

SCREENER_SYSTEM = """You are a sharia compliance screener applying AAOIFI standards.

AUTOMATICALLY NON-COMPLIANT (exclude immediately):
- Conventional banks, investment banks, insurance companies (interest-based)
- Alcohol producers, distributors, or retailers (primary business)
- Tobacco companies
- Weapons / defense contractors (primary business)
- Adult entertainment
- Pork production / processing

AUTOMATICALLY COMPLIANT (primary business is halal):
- Pure technology (software, semiconductors, hardware, cloud)
- Biotech, pharma, medical devices, healthcare services
- E-commerce (non-alcohol, non-pork primary goods)
- Payment networks (Visa, Mastercard — fee-based, not interest-based lending)
- Consumer goods (non-alcohol, non-pork)
- Energy (oil & gas extraction, renewables)
- Industrials (non-weapons manufacturing)
- Logistics, transportation

NEEDS_REVIEW (mixed or uncertain — Analyst will do deep check with full financials):
- Media / entertainment companies (check for adult content)
- Diversified conglomerates (check revenue mix)
- Any company where you are unsure

OUTPUT: JSON object mapping each ticker to one of: "compliant", "non_compliant", "needs_review"
Example: {"AAPL": "compliant", "JPM": "non_compliant", "DIS": "needs_review"}
Return JSON only, no explanation."""


def bulk_screen(tickers: list[str]) -> dict[str, str]:
    """
    Classify tickers in batches of 80 using Claude.
    Returns dict of ticker → 'compliant' | 'non_compliant' | 'needs_review'
    """
    results = {}
    batch_size = 80

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        user_msg = f"Classify these tickers:\n{json.dumps(batch)}\n\nReturn JSON only."
        try:
            batch_result = complete(SCREENER_SYSTEM, user_msg, as_json=True)
            if isinstance(batch_result, dict):
                results.update(batch_result)
        except Exception as e:
            print(f"  Sharia screener batch {i//batch_size + 1} failed: {e}")
            # Default unknown tickers to needs_review so Analyst handles them
            for ticker in batch:
                if ticker not in results:
                    results[ticker] = "needs_review"

    # Fill any missing tickers
    for ticker in tickers:
        if ticker not in results:
            results[ticker] = "needs_review"

    return results
