"""
fetch_elo.py — World Football Elo Ratings
==========================================
Computes Elo ratings from martj42 international results dataset.
Fixed: handles NaN values in scores and neutral field.
"""

import requests
import pandas as pd
import json
import os
import sys
import numpy as np
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import TEAM_ALIASES

MARTJ42_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"

# Current Elo baseline estimates (June 2026) — used as fallback
BASELINE_ELO = {
    "Argentina": 2090, "France": 2055, "Spain": 2050, "England": 2010,
    "Brazil": 2005, "Belgium": 1970, "Portugal": 1960, "Germany": 1955,
    "Netherlands": 1940, "Italy": 1935, "Croatia": 1905, "Uruguay": 1890,
    "Denmark": 1880, "Mexico": 1870, "USA": 1850, "Senegal": 1840,
    "Morocco": 1845, "Colombia": 1835, "Ecuador": 1800, "Japan": 1810,
    "South Korea": 1795, "Switzerland": 1810, "Austria": 1800, "Turkey": 1790,
    "Serbia": 1785, "Chile": 1780, "Australia": 1760, "Iran": 1765,
    "Canada": 1750, "Paraguay": 1730, "Czech Republic": 1740, "Hungary": 1735,
    "Slovakia": 1730, "Algeria": 1725, "Ivory Coast": 1720, "Nigeria": 1715,
    "Egypt": 1710, "Saudi Arabia": 1680, "South Africa": 1660,
    "Bosnia and Herzegovina": 1700, "Venezuela": 1650, "Jordan": 1620,
    "Indonesia": 1580, "New Zealand": 1570, "Kenya": 1520, "Qatar": 1560,
    "Norway": 1820, "Sweden": 1790, "Scotland": 1760, "Ghana": 1700,
    "Cameroon": 1690, "Tunisia": 1680, "Mali": 1660, "Senegal": 1840,
    "Iraq": 1640, "Haiti": 1560, "Panama": 1650, "Costa Rica": 1680,
    "Cuba": 1510, "Curacao": 1530, "Cape Verde": 1590,
}


def normalize_team(name):
    if not isinstance(name, str):
        return str(name) if name else ""
    return TEAM_ALIASES.get(name, name)


def compute_elo_ratings(results_df: pd.DataFrame,
                        k_wc=60, k_q=50, k_friendly=30) -> dict:
    """Compute Elo ratings handling NaN values safely."""
    elo = {}
    HOME_ADV = 100

    # Sort by date
    results_df = results_df.copy()
    results_df["date"] = pd.to_datetime(results_df["date"], errors="coerce")
    results_df = results_df.dropna(subset=["date"]).sort_values("date")

    for _, row in results_df.iterrows():
        home = normalize_team(row.get("home_team", ""))
        away = normalize_team(row.get("away_team", ""))
        if not home or not away:
            continue

        # Safe score extraction — skip NaN
        try:
            home_score = row.get("home_score", np.nan)
            away_score = row.get("away_score", np.nan)
            if pd.isna(home_score) or pd.isna(away_score):
                continue
            home_score = int(home_score)
            away_score = int(away_score)
        except (ValueError, TypeError):
            continue

        tournament = str(row.get("tournament", "")).lower()

        # Safe neutral extraction
        try:
            neutral_val = row.get("neutral", False)
            if pd.isna(neutral_val):
                is_neutral = False
            else:
                is_neutral = bool(neutral_val)
        except Exception:
            is_neutral = False

        # Initialise
        if home not in elo:
            elo[home] = BASELINE_ELO.get(home, 1500)
        if away not in elo:
            elo[away] = BASELINE_ELO.get(away, 1500)

        # K-factor
        if "world cup" in tournament and "qualif" not in tournament:
            K = k_wc
        elif "qualif" in tournament or "qualifier" in tournament:
            K = k_q
        else:
            K = k_friendly

        home_elo_adj = elo[home] + (0 if is_neutral else HOME_ADV)

        exp_home = 1 / (1 + 10 ** ((elo[away] - home_elo_adj) / 400))
        exp_away = 1 - exp_home

        if home_score > away_score:
            act_home, act_away = 1.0, 0.0
        elif home_score < away_score:
            act_home, act_away = 0.0, 1.0
        else:
            act_home, act_away = 0.5, 0.5

        gd = abs(home_score - away_score)
        if gd == 0:
            gd_mult = 1.0
        elif gd == 1:
            gd_mult = 1.0
        elif gd == 2:
            gd_mult = 1.5
        else:
            gd_mult = (11 + gd) / 8

        elo[home] += K * gd_mult * (act_home - exp_home)
        elo[away] += K * gd_mult * (act_away - exp_away)

    return {k: round(v) for k, v in sorted(elo.items(), key=lambda x: -x[1])}


def get_elo_win_probability(elo_home, elo_away, neutral=True):
    """Convert Elo to win/draw/loss probabilities."""
    HOME_ADV = 0 if neutral else 65
    elo_diff = (elo_home + HOME_ADV) - elo_away
    p_home_win_raw = 1 / (1 + 10 ** (-elo_diff / 400))
    diff_scale = abs(elo_diff) / 400
    p_draw = max(0.05, min(0.26 * (1 - 0.5 * diff_scale), 0.30))
    remaining = 1 - p_draw
    p_home_win = p_home_win_raw * remaining
    p_away_win = (1 - p_home_win_raw) * remaining
    return round(p_home_win, 4), round(p_draw, 4), round(p_away_win, 4)


def main():
    os.makedirs("data/processed", exist_ok=True)

    print("\n=== Fetching Elo Ratings ===\n")

    try:
        print("  Fetching international results dataset...")
        df = pd.read_csv(MARTJ42_URL)
        print(f"  ✓ {len(df)} international matches loaded")

        print("  Computing Elo from full international history...")
        computed_elo = compute_elo_ratings(df)
        final_elo = {**BASELINE_ELO, **computed_elo}
        print(f"  ✓ Computed Elo for {len(computed_elo)} teams")

    except Exception as e:
        print(f"  ✗ Elo computation failed: {e} — using baseline")
        import traceback; traceback.print_exc()
        final_elo = BASELINE_ELO.copy()

    with open("data/processed/elo_ratings.json", "w") as f:
        json.dump(final_elo, f, indent=2)
    print(f"  ✓ Saved → data/processed/elo_ratings.json")

    print("\n  Top 20 Teams by Elo:")
    for i, (team, elo_val) in enumerate(list(final_elo.items())[:20], 1):
        print(f"    {i:2}. {team:<30} {elo_val}")

    print("\n  Sample probabilities:")
    samples = [
        ("Argentina", "Algeria"), ("France", "Senegal"),
        ("Spain", "Morocco"), ("England", "Nigeria"), ("Brazil", "Ecuador"),
    ]
    for h, a in samples:
        ph, pd_, pa = get_elo_win_probability(
            final_elo.get(h, 1700), final_elo.get(a, 1700), neutral=True)
        print(f"    {h} vs {a}: {ph:.1%} / {pd_:.1%} / {pa:.1%}")

    return final_elo


if __name__ == "__main__":
    elo = main()
    print(f"\n✅ Elo ratings ready — {len(elo)} teams")
