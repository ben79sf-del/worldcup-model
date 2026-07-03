# ⚽ World Cup 2026 Prediction Model

Dixon-Coles Poisson model for 2026 FIFA World Cup betting intelligence.
Mirrors your Tennis/MLB model architecture with GitHub storage + Netlify dashboard.

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set API keys
Either edit `config/config.py` directly or set environment variables:
```bash
export ODDS_API_KEY="your_key_here"
export FOOTBALL_DATA_KEY="your_key_here"
export GITHUB_TOKEN="your_token_here"
export GITHUB_REPO="username/worldcup-model"
```

### 3. Run first-time setup (fetches all data + trains model)
```bash
python run_daily.py --force --train
```

### 4. Daily run (refresh odds + predictions only)
```bash
python run_daily.py
```

### 5. Quick odds refresh only
```bash
python run_daily.py --odds-only
```

---

## Project Structure

```
worldcup_model/
├── config/
│   └── config.py              # API keys, settings, team data
├── data/
│   ├── fetch_results.py       # football-data.org historical results
│   ├── fetch_elo.py           # World Football Elo ratings
│   └── fetch_odds.py          # The Odds API (moneyline, AH, totals)
├── models/
│   └── dixon_coles_model.py   # Bivariate Poisson model (core algorithm)
├── predictions/
│   ├── predictions_engine.py  # Edge detection + Kelly sizing
│   └── github_storage.py      # Push to GitHub repo
├── dashboard/
│   └── index.html             # Netlify dashboard
├── run_daily.py               # Main orchestrator
└── requirements.txt
```

---

## Model Details

### Algorithm: Dixon-Coles (1997)
- Goals modelled as independent Poisson processes
- `λ_home = attack_home × defense_away × μ × exp(home_adv)`
- `λ_away = attack_away × defense_home × μ`
- Low-score correction (ρ) adjusts 0-0, 1-0, 0-1, 1-1 probabilities
- Parameters fitted via Maximum Likelihood Estimation
- Time decay: exponential weight (recent matches weighted higher)

### Training Data
- Past World Cups: 2010, 2014, 2018, 2022
- Euros: 2012, 2016, 2020, 2024
- Copa America: 2021, 2024
- World Cup Qualifiers (via martj42 dataset)

### Match Weights by Competition
| Competition | Weight |
|---|---|
| World Cup | 1.0 |
| WC Qualifiers | 0.9 |
| Euros / Copa | 0.85 |
| Nations League | 0.75 |
| Friendlies | 0.3 |

### Markets Covered
- ✅ Moneyline (1X2 / Home-Draw-Away)
- ✅ Asian Handicap (all main lines)
- ✅ Total Goals Over/Under (0.5 through 4.5)
- ✅ Both Teams To Score (BTTS)
- ✅ Correct Score / Top Scorelines

### Edge Thresholds
- 🔥 **Strong**: ≥ 8% edge
- ✅ **Good**: ≥ 5% edge  
- 👀 **Watch**: ≥ 3.5% edge

---

## Dashboard Setup (Netlify)

1. Push this repo to GitHub
2. Connect repo to Netlify
3. Set publish directory: `dashboard/`
4. In `dashboard/index.html`, update `PREDICTIONS_URL` to your repo's raw URL:
   ```
   https://raw.githubusercontent.com/YOUR_USERNAME/worldcup-model/main/predictions/latest.json
   ```

---

## Known Limitations

International football is inherently harder to model than club football:
- **Small sample**: ~10 competitive matches per team per year
- **Squad turnover**: Players change significantly every 4 years
- **Best markets**: Totals and AH for clear mismatches; value bets on favorites vs weaker teams
- **Worst markets**: Corners (insufficient historical style data)
- **Lineup dependency**: No squad availability data until matchday

Use predictions as a starting point, not gospel. Always cross-reference with:
- Team news / injury reports
- Tournament form (first match nerves, advancement situations)
- Historical head-to-head trends
