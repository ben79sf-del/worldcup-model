"""
fetch_results.py — Pull historical international match data
============================================================
Primary source: martj42/international_results (49,000+ matches, free, no key)
Supplement:     football-data.org (Euro 2024, WC 2026 fixtures)
"""

import requests
import pandas as pd
import json
import os
import time
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import FD_BASE_URL, FOOTBALL_DATA_KEY, TEAM_ALIASES

FD_HEADERS = {"X-Auth-Token": FOOTBALL_DATA_KEY}

# Primary dataset — full international history from GitHub (no key needed)
MARTJ42_RESULTS_URL  = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
MARTJ42_SHOOTOUTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/shootouts.csv"

# Only use matches from 2010 onwards for relevance
MIN_YEAR = 2010

# Competition weight mapping
COMP_WEIGHTS = {
    "fifa world cup":              1.00,
    "world cup":                   1.00,
    "fifa world cup qualification":0.90,
    "world cup qualification":     0.90,
    "wc qualification":            0.90,
    "uefa euro":                   0.85,
    "uefa european championship":  0.85,
    "copa america":                0.85,
    "africa cup of nations":       0.80,
    "afc asian cup":               0.80,
    "concacaf gold cup":           0.75,
    "uefa nations league":         0.75,
    "nations league":              0.75,
    "friendly":                    0.10,  # Dropped from 0.3 — friendlies are uninformative
    "friendlies":                  0.10,
}

def get_comp_weight(tournament: str) -> float:
    t = tournament.lower().strip()
    for key, weight in COMP_WEIGHTS.items():
        if key in t:
            return weight
    # Default: treat unknown tournaments as mid-weight
    return 0.60

def normalize_team(name: str) -> str:
    return TEAM_ALIASES.get(name, name)

def fetch_martj42_results() -> pd.DataFrame:
    """Fetch full international results from martj42 GitHub dataset."""
    print("  Fetching martj42 international results dataset...")
    try:
        df = pd.read_csv(MARTJ42_RESULTS_URL)
        print(f"  Raw rows: {len(df)}")

        # Filter to MIN_YEAR onwards
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df[df["date"].dt.year >= MIN_YEAR].copy()
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        # Drop rows with missing scores
        df = df.dropna(subset=["home_score", "away_score"])
        df["home_score"] = df["home_score"].astype(int)
        df["away_score"] = df["away_score"].astype(int)

        # Normalize team names
        df["home_team"] = df["home_team"].apply(normalize_team)
        df["away_team"] = df["away_team"].apply(normalize_team)

        # Add weight
        df["weight"] = df["tournament"].apply(get_comp_weight)

        # Add result columns
        df["result"] = df.apply(
            lambda r: "H" if r["home_score"] > r["away_score"]
                      else ("A" if r["home_score"] < r["away_score"] else "D"), axis=1
        )
        df["total_goals"]  = df["home_score"] + df["away_score"]
        df["goal_diff"]    = df["home_score"] - df["away_score"]
        df["btts"]         = ((df["home_score"] > 0) & (df["away_score"] > 0)).astype(int)
        df["over_2_5"]     = (df["total_goals"] > 2.5).astype(int)
        df["over_3_5"]     = (df["total_goals"] > 3.5).astype(int)
        df["home_win"]     = (df["result"] == "H").astype(int)
        df["draw"]         = (df["result"] == "D").astype(int)
        df["away_win"]     = (df["result"] == "A").astype(int)

        # Rename columns to match model expectations
        df = df.rename(columns={
            "home_score": "home_goals",
            "away_score": "away_goals",
            "tournament": "competition",
        })

        # Keep only needed columns
        cols = ["date","competition","weight","home_team","away_team",
                "home_goals","away_goals","total_goals","goal_diff",
                "result","btts","over_2_5","over_3_5",
                "home_win","draw","away_win","neutral"]
        df = df[[c for c in cols if c in df.columns]]

        print(f"  ✓ {len(df)} matches from {MIN_YEAR} onwards")
        print(f"  Teams: {df['home_team'].nunique()} unique")
        print(f"  Date range: {df['date'].min()} → {df['date'].max()}")

        # Show competition breakdown
        comp_counts = df.groupby("competition").size().sort_values(ascending=False).head(10)
        print("\n  Top competitions:")
        for comp, count in comp_counts.items():
            w = get_comp_weight(comp)
            print(f"    {comp:<45} {count:>5} matches  (weight {w:.2f})")

        return df

    except Exception as e:
        print(f"  ✗ martj42 fetch failed: {e}")
        import traceback; traceback.print_exc()
        return pd.DataFrame()


def fetch_wc2026_fixtures() -> list:
    """Fetch 2026 WC schedule from football-data.org."""
    url = f"{FD_BASE_URL}/competitions/WC/matches"
    params = {"season": 2026}
    try:
        r = requests.get(url, headers=FD_HEADERS, params=params, timeout=15)
        r.raise_for_status()
        matches = r.json().get("matches", [])
        print(f"  ✓ WC 2026: {len(matches)} matches fetched")
        return matches
    except Exception as e:
        print(f"  ✗ WC 2026 fetch error: {e}")
        return []


def fetch_team_recent_form(team_name: str, matches_df: pd.DataFrame, n: int = 15) -> dict:
    """Calculate recent form metrics for a team."""
    team_matches = matches_df[
        (matches_df["home_team"] == team_name) |
        (matches_df["away_team"] == team_name)
    ].copy()
    team_matches = team_matches.sort_values("date", ascending=False).head(n)

    if len(team_matches) == 0:
        return {"attack": 1.0, "defense": 1.0, "form_pts": 0, "n_matches": 0}

    goals_scored, goals_conceded, points = [], [], []
    for _, row in team_matches.iterrows():
        w = row.get("weight", 1.0)
        if row["home_team"] == team_name:
            gs, gc = row["home_goals"], row["away_goals"]
            pts = 3 if row["result"] == "H" else (1 if row["result"] == "D" else 0)
        else:
            gs, gc = row["away_goals"], row["home_goals"]
            pts = 3 if row["result"] == "A" else (1 if row["result"] == "D" else 0)
        goals_scored.append(gs * w)
        goals_conceded.append(gc * w)
        points.append(pts * w)

    LEAGUE_AVG = 1.3
    avg_scored   = sum(goals_scored) / len(goals_scored)
    avg_conceded = sum(goals_conceded) / len(goals_conceded)
    avg_pts      = sum(points) / len(points)

    return {
        "attack":       round(avg_scored / LEAGUE_AVG, 4),
        "defense":      round(LEAGUE_AVG / max(avg_conceded, 0.1), 4),
        "avg_scored":   round(avg_scored, 4),
        "avg_conceded": round(avg_conceded, 4),
        "form_pts":     round(avg_pts, 4),
        "n_matches":    len(team_matches),
    }


def main():
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)

    print("\n=== Fetching Historical Match Data ===\n")

    # Primary: martj42 dataset
    df = fetch_martj42_results()

    if df.empty:
        print("  ✗ No data fetched — check internet connection")
        return None, [], {}

    # Save
    df.to_csv("data/raw/historical_matches.csv", index=False)
    print(f"\n  ✓ Saved {len(df)} matches → data/raw/historical_matches.csv")

    # Fetch WC 2026 fixtures
    print("\n=== Fetching 2026 WC Schedule ===\n")
    wc_matches = fetch_wc2026_fixtures()

    upcoming = []
    for m in wc_matches:
        if m.get("status") not in ("SCHEDULED", "TIMED"):
            continue
        try:
            upcoming.append({
                "fixture_id": m.get("id"),
                "date":       m.get("utcDate", "")[:10],
                "time":       m.get("utcDate", "")[11:16],
                "competition":"WC",
                "matchday":   m.get("matchday"),
                "group":      m.get("group", ""),
                "home_team":  normalize_team(m["homeTeam"]["name"]),
                "away_team":  normalize_team(m["awayTeam"]["name"]),
                "venue":      m.get("venue", ""),
                "status":     m.get("status"),
            })
        except Exception:
            pass

    with open("data/raw/wc2026_fixtures.json", "w") as f:
        json.dump(upcoming, f, indent=2)
    print(f"  ✓ Saved {len(upcoming)} upcoming WC fixtures")

    # Build team ratings
    print("\n=== Building Team Ratings ===\n")
    all_teams = set(df["home_team"].tolist() + df["away_team"].tolist())
    ratings = {}
    for team in sorted(all_teams):
        ratings[team] = fetch_team_recent_form(team, df)

    with open("data/processed/team_ratings.json", "w") as f:
        json.dump(ratings, f, indent=2)
    print(f"  ✓ Built ratings for {len(ratings)} teams")

    return df, upcoming, ratings


if __name__ == "__main__":
    df, fixtures, ratings = main()
    if df is not None:
        print(f"\n✅ Done — {len(df)} matches, {len(fixtures)} upcoming fixtures")
