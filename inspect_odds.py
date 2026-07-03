"""
inspect_odds.py — Check what markets/lines exist for a specific match
========================================================================
Run from your World Cup MOdel folder:
    python inspect_odds.py
"""

import json

with open("data/raw/odds_latest.json") as f:
    odds = json.load(f)

# Find Qatar vs Switzerland (or any team name variant)
target_keys = [k for k in odds.keys() if "Qatar" in k]

if not target_keys:
    print("No match found containing 'Qatar' in odds_latest.json")
    print("\nAvailable match keys:")
    for k in list(odds.keys())[:10]:
        print(f"  {k}")
else:
    for k in target_keys:
        print(f"\n{'='*60}")
        print(f"  {k}")
        print(f"{'='*60}")
        match = odds[k]

        print("\n--- TOTALS ---")
        totals = match.get("totals", {}).get("totals", {})
        if totals:
            for line_key, line_data in totals.items():
                print(f"  {line_key}: avg_implied={line_data.get('avg_implied')}, "
                      f"best_decimal={line_data.get('best_decimal')}, "
                      f"n_books={line_data.get('n_books')}")
        else:
            print("  (empty -- no totals lines found)")

        print("\n--- SPREADS (Asian Handicap) ---")
        spreads = match.get("spreads", {}).get("spreads", {})
        if spreads:
            for line_key, line_data in list(spreads.items())[:5]:
                print(f"  {line_key}: {line_data}")
        else:
            print("  (empty)")

        print("\n--- H2H (1X2) ---")
        h2h = match.get("h2h", {})
        books = h2h.get("books", {})
        print(f"  Bookmakers with odds: {list(books.keys())}")
        print(f"  Consensus: {h2h.get('consensus', {})}")
