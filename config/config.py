"""
World Cup 2026 Model — Configuration
=====================================
Set your API keys as environment variables or paste directly for local use.
"""

import os

# ── API Keys ──────────────────────────────────────────────────────────────────
ODDS_API_KEY        = os.getenv("ODDS_API_KEY", "a613bfad0e47fafb085b774c856f6ca6")
FOOTBALL_DATA_KEY   = os.getenv("FOOTBALL_DATA_KEY", "842edd0be39d4e59ba3db132fafc3840")

# ── The Odds API ───────────────────────────────────────────────────────────────
ODDS_BASE_URL       = "https://api.the-odds-api.com/v4"
ODDS_SPORT          = "soccer_fifa_world_cup"
ODDS_REGIONS        = "us,uk,eu,au"
ODDS_MARKETS        = "h2h,spreads,totals"           # moneyline, asian handicap, totals
ODDS_BOOKMAKERS     = "pinnacle,bet365,draftkings,fanduel,betmgm"

# ── Football-Data.org ──────────────────────────────────────────────────────────
FD_BASE_URL         = "https://api.football-data.org/v4"
FD_COMPETITION_WC   = "WC"          # 2026 World Cup
FD_COMPETITION_EC   = "EC"          # Euro (signal data)
FD_COMPETITION_CL   = "CL"          # Champions League (player form)

# ── ClubElo API (free, no key needed) ─────────────────────────────────────────
CLUBELO_BASE_URL    = "http://api.clubelo.com"

# ── Model Settings ─────────────────────────────────────────────────────────────
MIN_EDGE_PCT        = 6.0           # Raised from 3.5 — WATCH tier bets were noise
MAX_EDGE_PCT        = 30.0          # Maximum % edge -- above this, model/market disagreement is too extreme to be real value
KELLY_FRACTION      = 0.25          # Quarter Kelly for bankroll sizing
MAX_KELLY           = 0.05          # Cap at 5% of bankroll per bet
DAILY_STAKE_CAP     = 20.0          # Maximum units staked per day across all value bets
FORM_WINDOW         = 15            # Last N matches for form calculation
FORM_WEIGHTS = {                    # Weight by match type
    "WC":               1.0,        # World Cup
    "WCQ":              0.9,        # World Cup Qualifiers
    "EURO":             0.85,       # Euros
    "COPA":             0.85,       # Copa America
    "NL":               0.75,       # Nations League
    "FRIENDLY":         0.3,        # Friendlies — low weight
}

# ── GitHub Storage ─────────────────────────────────────────────────────────────
GITHUB_TOKEN        = os.getenv("GITHUB_TOKEN", "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")
GITHUB_REPO         = os.getenv("GITHUB_REPO", "ben79sf-del/worldcup-model")
GITHUB_BRANCH       = "main"
PREDICTIONS_PATH    = "predictions/latest.json"
HISTORY_PATH        = "predictions/history.json"

# ── 2026 World Cup — All 48 Teams + Groups ─────────────────────────────────────
WC_GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Germany", "Japan", "Chile", "Saudi Arabia"],
    "D": ["USA", "Paraguay", "Australia", "Turkey"],
    "E": ["Spain", "Morocco", "Venezuela", "Kenya"],
    "F": ["France", "Mali", "Egypt", "Uruguay"],        # Update from official draw
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Portugal", "Senegal", "Indonesia", "Serbia"],
    "I": ["England", "Slovakia", "Nigeria", "Trinidad and Tobago"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["Brazil", "Ecuador", "Ivory Coast", "Hungary"],
}

# Team name aliases (football-data.org → common name)
TEAM_ALIASES = {
    "United States": "USA",
    "United States of America": "USA",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "DR Congo": "Congo DR",
    "Congo DR": "DR Congo",
    "Cape Verde Islands": "Cape Verde",
    "Cote d'Ivoire": "Ivory Coast",
}

# ── Output Paths ───────────────────────────────────────────────────────────────
DATA_DIR            = "data/raw"
PROCESSED_DIR       = "data/processed"
PREDICTIONS_DIR     = "predictions"
DASHBOARD_DIR       = "dashboard"
