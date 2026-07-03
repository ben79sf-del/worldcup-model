"""
run_daily.py — World Cup 2026 Daily Prediction Pipeline
========================================================
Run this once per day (or before each matchday) to:
  1. Fetch latest odds
  2. Refresh team form data
  3. Generate predictions for upcoming matches
  4. Identify value bets
  5. Push results to GitHub → Netlify dashboard

Usage:
  python run_daily.py              # Full run
  python run_daily.py --odds-only  # Just refresh odds
  python run_daily.py --predict    # Just run predictions (use cached data)
  python run_daily.py --train      # Retrain Dixon-Coles model
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

# Force UTF-8 console output on Windows so emoji in print() statements
# don't crash with UnicodeEncodeError (cp1252 codec)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure imports work from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.config import (
    ODDS_API_KEY, FOOTBALL_DATA_KEY, GITHUB_TOKEN, GITHUB_REPO
)


def check_config():
    """Validate all required config is set."""
    errors = []
    if ODDS_API_KEY == "YOUR_ODDS_API_KEY":
        errors.append("ODDS_API_KEY not set")
    if FOOTBALL_DATA_KEY == "YOUR_FOOTBALL_DATA_KEY":
        errors.append("FOOTBALL_DATA_KEY not set")
    if GITHUB_TOKEN == "YOUR_GITHUB_TOKEN":
        errors.append("GITHUB_TOKEN not set (predictions won't be pushed)")
    
    if errors:
        print("⚠ Configuration warnings:")
        for e in errors:
            print(f"  - {e}")
        print("  Set these in config/config.py or as environment variables\n")
    
    return len([e for e in errors if "GITHUB" not in e]) == 0


def step_fetch_results(force: bool = False):
    """Step 1: Fetch historical results + 2026 fixtures."""
    hist_path = "data/raw/historical_matches.csv"
    fixtures_path = "data/raw/wc2026_fixtures.json"
    
    if not force and os.path.exists(hist_path) and os.path.exists(fixtures_path):
        print("  ✓ Historical data exists (use --force to re-fetch)")
        return True
    
    print("  Fetching historical match data...")
    from data.fetch_results import main as fetch_results
    try:
        fetch_results()
        return True
    except Exception as e:
        print(f"  ✗ Results fetch failed: {e}")
        return False


def step_fetch_elo(force: bool = False):
    """Step 2: Update Elo ratings."""
    elo_path = "data/processed/elo_ratings.json"
    
    if not force and os.path.exists(elo_path):
        print("  ✓ Elo ratings exist (use --force to re-fetch)")
        return True
    
    print("  Fetching Elo ratings...")
    from data.fetch_elo import main as fetch_elo
    try:
        fetch_elo()
        return True
    except Exception as e:
        print(f"  ✗ Elo fetch failed: {e}")
        return False


def step_train_model(force: bool = False):
    """Step 3: Train / refresh Dixon-Coles model."""
    model_path = "models/dixon_coles_params.json"
    
    if not force and os.path.exists(model_path):
        print("  ✓ Model exists (use --train to retrain)")
        return True
    
    print("  Training Dixon-Coles model (30–60s)...")
    from models.dixon_coles_model import main as train_model
    try:
        train_model()
        return True
    except Exception as e:
        print(f"  ✗ Model training failed: {e}")
        return False


def step_fetch_odds():
    """Step 4: Fetch latest odds (always refresh)."""
    print("  Fetching live odds...")
    from data.fetch_odds import main as fetch_odds
    try:
        fetch_odds()
        return True
    except Exception as e:
        print(f"  ✗ Odds fetch failed: {e}")
        return False


def step_patch_fixtures_from_odds():
    """
    Step 4b: Fill in missing team names in wc2026_fixtures.json using
    confirmed matchups from the odds feed.

    football-data.org's knockout bracket often lags behind reality —
    it can show null/TBD team slots for days after the matchup is
    actually decided and bookmakers have posted odds. The Odds API
    reflects the real bracket faster, so we use it as a patch source,
    matched by kickoff date (since fixture_ids and exact timestamps
    can differ slightly between the two providers).
    """
    fixtures_path = "data/raw/wc2026_fixtures.json"
    odds_path = "data/raw/odds_latest.json"

    if not os.path.exists(fixtures_path) or not os.path.exists(odds_path):
        print("  ⚠ Skipping fixture patch — missing fixtures or odds file")
        return False

    with open(fixtures_path, "r", encoding="utf-8") as f:
        fixtures = json.load(f)
    with open(odds_path, "r", encoding="utf-8") as f:
        odds = json.load(f)

    # Normalise odds feed team names to match fixtures naming conventions
    ODDS_ALIASES = {
        "Bosnia & Herzegovina": "Bosnia and Herzegovina",
        "DR Congo": "Congo DR",
        "Cape Verde Islands": "Cape Verde",
        "Cote d\'Ivoire": "Ivory Coast",
        "United States": "USA",
    }
    def normalise(name):
        return ODDS_ALIASES.get(name, name) if name else name

    # Build a lookup of confirmed matchups from odds, keyed by date (YYYY-MM-DD)
    # A single date can have multiple matches, so store a list per date.
    odds_by_date = {}
    for key, match in odds.items():
        commence = match.get("commence_time", "")
        date = commence[:10]
        if not date:
            continue
        odds_by_date.setdefault(date, []).append({
            "home_team": normalise(match.get("home_team")),
            "away_team": normalise(match.get("away_team")),
        })

    patched = 0
    used_odds_pairs = set()  # avoid assigning the same odds match twice

    for fx in fixtures:
        has_home = bool(fx.get("home_team"))
        has_away = bool(fx.get("away_team"))
        if has_home and has_away:
            continue  # already complete, nothing to patch

        date = fx.get("date", "")
        candidates = odds_by_date.get(date, [])

        for cand in candidates:
            pair_key = (date, cand["home_team"], cand["away_team"])
            if pair_key in used_odds_pairs:
                continue

            # Case 1: both missing — only safe to fill if exactly one
            # unmatched odds candidate exists for that date (avoid guessing
            # which of several same-day matches this fixture is)
            if not has_home and not has_away:
                same_day_unfilled = [
                    f for f in fixtures
                    if f.get("date") == date and not f.get("home_team") and not f.get("away_team")
                ]
                unused_candidates = [c for c in candidates if (date, c["home_team"], c["away_team"]) not in used_odds_pairs]
                if len(same_day_unfilled) == 1 and len(unused_candidates) == 1:
                    fx["home_team"] = cand["home_team"]
                    fx["away_team"] = cand["away_team"]
                    used_odds_pairs.add(pair_key)
                    patched += 1
                    break
                continue

            # Case 2: one side known — match odds candidate containing that team
            known_team = fx.get("home_team") or fx.get("away_team")
            if known_team in (cand["home_team"], cand["away_team"]):
                fx["home_team"] = cand["home_team"]
                fx["away_team"] = cand["away_team"]
                used_odds_pairs.add(pair_key)
                patched += 1
                break

    if patched:
        with open(fixtures_path, "w", encoding="utf-8") as f:
            json.dump(fixtures, f, indent=2)
        print(f"  ✓ Patched {patched} fixture(s) with confirmed teams from odds feed")
    else:
        print("  ✓ No fixtures needed patching")

    return True


def step_generate_predictions():
    """Step 5: Generate predictions for upcoming fixtures."""
    print("  Generating predictions...")
    from predictions.predictions_engine import main as run_predictions
    try:
        output = run_predictions()
        return output
    except Exception as e:
        print(f"  ✗ Prediction generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def step_push_to_github(predictions_output: dict):
    """Step 6: Push predictions to GitHub."""
    print("  Pushing to GitHub...")
    from predictions.github_storage import push_predictions
    try:
        success = push_predictions(predictions_output)
        return success
    except Exception as e:
        print(f"  ✗ GitHub push failed: {e}")
        return False


def step_track_results(push: bool = True):
    """Step 7: Score finished matches against past predictions."""
    print("  Checking for finished matches...")
    from tracking.results_tracker import main as run_tracker
    try:
        log = run_tracker()
        if push:
            from predictions.github_storage import push_results_log
            push_results_log(log)
        return log
    except Exception as e:
        print(f"  ✗ Results tracking failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def build_summary(predictions_output: dict) -> str:
    """Build a text summary of today's predictions."""
    if not predictions_output:
        return "No predictions available."
    
    preds = predictions_output.get("predictions", [])
    total_vb = sum(len(p.get("value_bets", [])) for p in preds)
    
    lines = [
        f"\n{'='*60}",
        f"  🌍 WORLD CUP 2026 — Daily Predictions",
        f"  {datetime.utcnow().strftime('%A, %B %d %Y')}",
        f"{'='*60}",
        f"  Fixtures predicted: {len(preds)}",
        f"  Value bets found:   {total_vb}",
        "",
    ]
    
    # Group by date
    by_date = {}
    for pred in preds:
        d = pred.get("match_meta", {}).get("date", "Unknown")
        by_date.setdefault(d, []).append(pred)
    
    for date in sorted(by_date.keys()):
        lines.append(f"  📅 {date}")
        for pred in by_date[date]:
            h = pred["home_team"]
            a = pred["away_team"]
            m = pred["model"]
            group = pred.get("match_meta", {}).get("group", "")
            vb = pred.get("value_bets", [])
            
            lines.append(
                f"    {h} vs {a}"
                + (f" (Group {group})" if group else "")
            )
            lines.append(
                f"      1X2: {m['p_home_win']:.1%} / {m['p_draw']:.1%} / {m['p_away_win']:.1%}"
                f"  |  xG: {m['lambda_home']:.2f}–{m['lambda_away']:.2f}"
                f"  |  O2.5: {m.get('p_over_2_5', 0):.1%}"
            )
            if vb:
                top = vb[0]
                lines.append(
                    f"      {top['rating']} {top['market']} @ {top['best_odds']} "
                    f"(edge: {top['edge_pct']:+.1f}%, Kelly: {top['kelly_pct']:.1f}%)"
                )
        lines.append("")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="World Cup 2026 Prediction Pipeline")
    parser.add_argument("--odds-only",  action="store_true", help="Only refresh odds")
    parser.add_argument("--predict",    action="store_true", help="Only run predictions (cached data)")
    parser.add_argument("--train",      action="store_true", help="Force model retrain")
    parser.add_argument("--no-push",    action="store_true", help="Skip GitHub push")
    parser.add_argument("--force",      action="store_true", help="Re-fetch all data")
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"  🌍 World Cup 2026 Model — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")
    
    # Check config
    if not check_config():
        print("✗ Missing required API keys. Exiting.")
        return
    
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    os.makedirs("predictions", exist_ok=True)
    
    if args.odds_only:
        print("── Step: Refresh Odds Only ──\n")
        step_fetch_odds()
        step_patch_fixtures_from_odds()
        return
    
    if not args.predict:
        # Full pipeline
        print("── Step 1: Historical Results ──\n")
        step_fetch_results(force=args.force)
        time.sleep(1)
        
        print("\n── Step 2: Elo Ratings ──\n")
        step_fetch_elo(force=args.force)
        time.sleep(1)
        
        print("\n── Step 3: Model Training ──\n")
        step_train_model(force=args.train)
        time.sleep(1)
        
        print("\n── Step 4: Live Odds ──\n")
        step_fetch_odds()
        time.sleep(1)

        print("\n── Step 4b: Patch Fixtures From Odds ──\n")
        step_patch_fixtures_from_odds()
        time.sleep(1)
    
    print("\n── Step 5: Predictions ──\n")
    output = step_generate_predictions()
    
    if output:
        summary = build_summary(output)
        print(summary)
        
        # Save summary
        with open("predictions/daily_summary.txt", "w", encoding="utf-8") as f:
            f.write(summary)
        
        if not args.no_push:
            print("\n── Step 6: GitHub Push ──\n")
            step_push_to_github(output)
        
        print("\n── Step 7: Results Tracking ──\n")
        step_track_results(push=not args.no_push)
        
        print("\n✅ Pipeline complete!\n")
    else:
        print("\n✗ Pipeline failed at prediction step")


if __name__ == "__main__":
    main()
