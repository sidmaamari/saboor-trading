#!/usr/bin/env python3
"""
Saboor — Autonomous Halal Trading Agent
Usage: python main.py <phase>

Phases:
  init       Initialize the SQLite database
  premarket  7:30 AM — build today's watchlist
  open       9:35 AM — execute trades
  midday     12:00 PM — reassess positions
  eod        3:30 PM — close tactical positions, send report
"""
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    phase = sys.argv[1].lower()

    if phase == "init":
        from db.queries import init_db
        init_db()

    elif phase == "premarket":
        from phases.premarket import run
        run()

    elif phase == "open":
        from phases.market_open import run
        run()

    elif phase == "midday":
        from phases.midday import run
        run()

    elif phase == "eod":
        from phases.eod import run
        run()

    else:
        print(f"Unknown phase: '{phase}'")
        print("Valid phases: init | premarket | open | midday | eod")
        sys.exit(1)


if __name__ == "__main__":
    main()
