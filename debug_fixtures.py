"""
debug_fixtures.py — Diagnose why finished matches aren't matching predictions
================================================================================
Run this from your World Cup MOdel folder:
    python debug_fixtures.py
"""

import json
import os

HISTORY_DIR = "predictions/history"

print("\n=== Checking predictions/history/ snapshots ===\n")

if not os.path.exists(HISTORY_DIR):
    print(f"✗ Directory not found: {HISTORY_DIR}")
else:
    for fname in sorted(os.listdir(HISTORY_DIR)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(HISTORY_DIR, fname)
        with open(fpath) as f:
            data = json.load(f)

        preds = data.get("predictions", [])
        print(f"📄 {fname}: {len(preds)} predictions")

        # Look for Mexico vs South Africa and South Korea vs Czech Republic
        for p in preds:
            home = p.get("home_team", "")
            away = p.get("away_team", "")
            meta = p.get("match_meta", {})
            fixture_id = meta.get("fixture_id")

            if home in ("Mexico", "South Korea") or away in ("South Africa", "Czech Republic"):
                print(f"   → {home} vs {away}")
                print(f"     fixture_id: {fixture_id}  (type: {type(fixture_id).__name__})")
                print(f"     match_meta: {meta}")
        print()

print("\n=== Target fixture IDs from football-data.org ===")
print("  Mexico vs South Africa: 537327")
print("  South Korea vs Czech Republic: 537328")
print("\nCompare the fixture_id values above to these targets.")
print("If they don't match (or are missing/null), that's the bug.")
