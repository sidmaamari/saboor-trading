#!/usr/bin/env python3
"""
Saboor — Autonomous Halal Investing Agent
Usage: python main.py <phase>

Phases:
  init       Verify the Supabase schema (tables are managed remotely)
  premarket  7:30 AM — sharia screen, research, build ownership candidates
  open       9:35 AM — review candidates and open positions, execute decisions
  midday     12:00 PM — monitor portfolio and urgent thesis/compliance changes
  eod        3:30 PM — record benchmark, send EOD report
"""
import sys
from dotenv import load_dotenv

load_dotenv(override=True)
load_dotenv(".env.local", override=True)


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
