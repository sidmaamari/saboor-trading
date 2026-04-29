"""
Pre-market phase — 7:30 AM ET
Builds the ranked ownership candidate list for the day.
"""
from datetime import date
from tools.alpaca_client import get_bars
from tools.sharia_screener import bulk_screen
from tools.macro_client import get_macro_snapshot
from agents.researcher import build_dossiers
from agents.analyst import score_stocks
from agents.notifier import send_premarket_report
from db.queries import save_watchlist, log_decision
from data.universe import get_universe


def run():
    today = date.today()
    print(f"\n{'='*50}")
    print(f"Saboor PRE-MARKET — {today}")
    print(f"{'='*50}")

    log_decision("premarket", None, "phase_start", f"Pre-market phase started for {today}")

    # ── Step 1: Full universe ─────────────────────────────────────────────────
    all_tickers = get_universe()
    print(f"\nUniverse: {len(all_tickers)} tickers")

    # ── Step 2: Sharia gate via Claude ───────────────────────────────────────
    print("Running Claude sharia compliance gate...")
    compliance = bulk_screen(all_tickers)

    confirmed_compliant = [t for t, s in compliance.items() if s == "compliant"]
    needs_review = [t for t, s in compliance.items() if s == "needs_review"]
    excluded = [t for t, s in compliance.items() if s == "non_compliant"]

    print(f"  Compliant: {len(confirmed_compliant)} | Needs review: {len(needs_review)} | Excluded: {len(excluded)}")

    # needs_review tickers proceed with sharia_status flagged so Analyst does deep check
    candidate_pool = [
        (t, "compliant") for t in confirmed_compliant
    ] + [
        (t, "needs_review") for t in needs_review
    ]

    # ── Step 3: Quick relative-strength screen — pick top 35 for research ────
    print("\nRunning entry-timing pre-screen...")
    momentum_scores = []

    for ticker, sharia_status in candidate_pool:
        try:
            bars = get_bars(ticker, days=35)
            if len(bars) < 31:
                continue
            return_30d = (bars[-1]["close"] - bars[-30]["close"]) / bars[-30]["close"] * 100
            momentum_scores.append((ticker, sharia_status, return_30d))
        except Exception as e:
            print(f"  Momentum pre-screen failed for {ticker}: {e}")

    momentum_scores.sort(key=lambda x: x[2], reverse=True)
    top_candidates = momentum_scores[:35]
    research_tickers = [(t, s) for t, s, _ in top_candidates]
    print(f"  Top {len(research_tickers)} candidates selected for deep research")

    # ── Step 4: yfinance dossiers ─────────────────────────────────────────────
    print("\nBuilding research dossiers via yfinance...")
    ticker_list = [t for t, _ in research_tickers]
    sharia_map = {t: s for t, s in research_tickers}
    dossiers = build_dossiers(ticker_list)

    # Attach sharia status to each dossier
    for d in dossiers:
        d["sharia_status"] = sharia_map.get(d["ticker"], "not_found")

    # ── Step 5: SPY 30-day return for relative strength ───────────────────────
    spy_bars = get_bars("SPY", days=35)
    spy_30d = (
        (spy_bars[-1]["close"] - spy_bars[-30]["close"]) / spy_bars[-30]["close"] * 100
        if len(spy_bars) >= 30 else 0.0
    )
    print(f"\nSPY 30-day return: {spy_30d:.2f}%")

    # ── Step 5b: Macro context ────────────────────────────────────────────────
    print("Fetching macro context...")
    macro = get_macro_snapshot()
    if macro.get("ten_year_yield_pct"):
        print(f"  10yr yield: {macro['ten_year_yield_pct']:.2f}% | "
              f"3mo: {macro.get('three_month_yield_pct', 'n/a')}% | "
              f"Spread: {macro.get('yield_curve_spread_pct', 'n/a')}%")

    # ── Step 6: Claude Analyst scores all dossiers ───────────────────────────
    print("\nScoring candidates via Claude Analyst...")
    scored = score_stocks(dossiers, spy_return_30d=spy_30d, macro=macro)

    excluded_count = len(top_candidates) - len(scored)

    if not scored:
        log_decision("premarket", None, "no_candidates", "No stocks passed scoring thresholds")
        send_premarket_report([], excluded_count)
        print("No stocks passed thresholds — watchlist empty for today.")
        return []

    # ── Step 7: Enforce quality threshold, rank, save top candidates ─────────
    def _meets_threshold(s: dict) -> bool:
        score = s.get("combined_score", 0)
        quality = s.get("quality_score", 0)
        return quality >= 60 and score >= 65

    qualified = [s for s in scored if _meets_threshold(s)]
    disqualified = [s["ticker"] for s in scored if not _meets_threshold(s)]
    if disqualified:
        print(f"  Post-filter removed {len(disqualified)} below-threshold: {disqualified}")

    qualified.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
    watchlist = qualified[:20]

    save_watchlist(today, watchlist)

    print(f"\nOwnership candidates ({len(watchlist)} stocks):")
    for s in watchlist:
        print(
            f"  {s['ticker']:6} | {s['combined_score']:5.1f} | {s['thesis'][:70]}"
        )

    below_threshold_count = len(scored) - len(qualified)
    send_premarket_report(watchlist, excluded_count + below_threshold_count)

    log_decision(
        "premarket", None, "phase_complete",
        f"Candidates: {[s['ticker'] for s in watchlist]}"
    )
    return watchlist
