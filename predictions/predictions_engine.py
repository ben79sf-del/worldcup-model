"""
predictions_engine.py — Find Value Bets vs Market Odds
=======================================================
Combines Dixon-Coles model probabilities with live odds
to identify edges across all markets.

Outputs structured predictions for the dashboard + GitHub.
"""

import json
import os
import sys
import math
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import MIN_EDGE_PCT, MAX_EDGE_PCT, KELLY_FRACTION, MAX_KELLY, DAILY_STAKE_CAP


def edge_pct(model_prob: float, market_implied: float) -> float:
    """
    Calculate % edge: model probability vs market implied probability.
    Positive = model likes the bet, negative = overpriced.
    """
    if market_implied <= 0 or market_implied >= 1:
        return 0.0
    return round((model_prob - market_implied) / market_implied * 100, 2)


def kelly_fraction(model_prob: float, decimal_odds: float) -> float:
    """
    Kelly Criterion: optimal bet size as fraction of bankroll.
    f = (bp - q) / b  where b = decimal_odds - 1, p = win prob, q = 1 - p
    Returns fractional Kelly (25%).
    """
    if decimal_odds <= 1.0 or model_prob <= 0:
        return 0.0
    b = decimal_odds - 1
    q = 1 - model_prob
    full_kelly = (b * model_prob - q) / b
    frac_kelly = full_kelly * KELLY_FRACTION
    return round(max(0, min(frac_kelly, MAX_KELLY)), 4)


def prob_to_american(prob: float) -> int:
    """Convert probability to American odds."""
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return round(-prob / (1 - prob) * 100)
    else:
        return round((1 - prob) / prob * 100)


def prob_to_decimal(prob: float) -> float:
    """Convert probability to decimal odds."""
    if prob <= 0:
        return 0
    return round(1 / prob, 3)


class PredictionEngine:
    """
    Generates predictions and value bets for World Cup matches.
    Combines Dixon-Coles model output with live market odds.
    """
    
    def __init__(self, model, elo_ratings: dict = None):
        self.model = model
        self.elo = elo_ratings or {}
    
    def predict_match(self, home: str, away: str,
                       odds_data: dict = None,
                       neutral: bool = True,
                       match_meta: dict = None) -> dict:
        """
        Full prediction + value bet analysis for a single match.
        """
        # ── Model Prediction ──────────────────────────────────────────────────
        pred = self.model.predict_match(home, away, neutral=neutral, elo_ratings=self.elo)
        
        result = {
            "home_team":     home,
            "away_team":     away,
            "neutral":       neutral,
            "match_meta":    match_meta or {},
            "model": {
                "source":            pred.get("data_source", "dixon_coles"),
                "lambda_home":       pred.get("lambda_home", 0),
                "lambda_away":       pred.get("lambda_away", 0),
                "expected_total":    pred.get("expected_total", 0),
                "p_home_win":        pred.get("p_home_win", 0),
                "p_draw":            pred.get("p_draw", 0),
                "p_away_win":        pred.get("p_away_win", 0),
                "p_over_2_5":        pred.get("p_over_2_5", 0),
                "p_under_2_5":       pred.get("p_under_2_5", 0),
                "p_over_3_5":        pred.get("p_over_3_5", 0),
                "p_btts":            pred.get("p_btts", 0),
                "p_no_btts":         pred.get("p_no_btts", 0),
                "most_likely_score": pred.get("most_likely_score", ""),
                "top_scorelines":    pred.get("top_scorelines", []),
                "asian_handicap":    pred.get("asian_handicap", {}),
            },
            "fair_odds": {
                "home_win_american":  prob_to_american(pred.get("p_home_win", 0.5)),
                "draw_american":      prob_to_american(pred.get("p_draw", 0.28)),
                "away_win_american":  prob_to_american(pred.get("p_away_win", 0.5)),
                "home_win_decimal":   prob_to_decimal(pred.get("p_home_win", 0.5)),
                "draw_decimal":       prob_to_decimal(pred.get("p_draw", 0.28)),
                "away_win_decimal":   prob_to_decimal(pred.get("p_away_win", 0.5)),
                "over_2_5_decimal":   prob_to_decimal(pred.get("p_over_2_5", 0.5)),
                "under_2_5_decimal":  prob_to_decimal(pred.get("p_under_2_5", 0.5)),
            },
            "value_bets": [],
            "market_comparison": {},
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        # ── Market Comparison + Value Bets ────────────────────────────────────
        result["market_odds"] = {}
        if odds_data:
            match_key = f"{home} vs {away}"
            match_odds = odds_data.get(match_key, {})
            
            if match_odds:
                result["market_comparison"] = self._compare_markets(pred, match_odds)
                result["value_bets"]        = self._find_value_bets(pred, match_odds)
                result["market_odds"]       = self._extract_market_odds(match_odds)
        
        # ── Summary Rating ─────────────────────────────────────────────────────
        result["confidence"] = self._confidence_score(pred)
        result["bet_recommendation"] = self._bet_recommendation(result["value_bets"])
        
        return result
    
    def _compare_markets(self, pred: dict, match_odds: dict) -> dict:
        """Compare model probabilities to market implied probabilities."""
        h2h = match_odds.get("h2h", {})
        consensus = h2h.get("consensus", {})
        totals = match_odds.get("totals", {})
        
        comparison = {}
        
        # 1X2
        if consensus.get("home_implied"):
            comparison["home_win"] = {
                "model_prob":    pred.get("p_home_win", 0),
                "market_prob":   consensus["home_implied"],
                "edge_pct":      edge_pct(pred.get("p_home_win", 0), consensus["home_implied"]),
                "best_odds":     match_odds.get("h2h", {}).get("best_home_odds", 0),
            }
        if consensus.get("draw_implied"):
            comparison["draw"] = {
                "model_prob":   pred.get("p_draw", 0),
                "market_prob":  consensus["draw_implied"],
                "edge_pct":     edge_pct(pred.get("p_draw", 0), consensus["draw_implied"]),
                "best_odds":    match_odds.get("h2h", {}).get("best_draw_odds", 0),
            }
        if consensus.get("away_implied"):
            comparison["away_win"] = {
                "model_prob":   pred.get("p_away_win", 0),
                "market_prob":  consensus["away_implied"],
                "edge_pct":     edge_pct(pred.get("p_away_win", 0), consensus["away_implied"]),
                "best_odds":    match_odds.get("h2h", {}).get("best_away_odds", 0),
            }
        
        # Over/Under
        for line_key, line_data in totals.get("totals", {}).items():
            if "over" in line_key:
                line_val = float(line_key.replace("Over_", "").replace("over_", "").replace("_over", ""))
                model_key = f"p_over_{str(line_val).replace('.', '_')}"
                model_p = pred.get(model_key, pred.get(f"p_over_{line_val:.1f}".replace(".", "_")))
                
                # Try standard keys
                if "2.5" in line_key or line_val == 2.5:
                    model_p = pred.get("p_over_2_5", 0)
                elif "3.5" in line_key or line_val == 3.5:
                    model_p = pred.get("p_over_3_5", 0)
                
                if model_p and line_data.get("avg_implied"):
                    comparison[f"over_{line_val}"] = {
                        "model_prob":   model_p,
                        "market_prob":  line_data["avg_implied"],
                        "edge_pct":     edge_pct(model_p, line_data["avg_implied"]),
                        "best_odds":    line_data.get("best_decimal", 0),
                    }
        
        return comparison
    
    def _extract_market_odds(self, match_odds: dict) -> dict:
        """
        Extract a simple, always-populated view of current market odds
        for 1X2, totals (2.5), and BTTS -- regardless of whether the
        model finds an "edge". This gives a full picture for the user
        to make their own judgment, not just flagged value bets.
        """
        h2h = match_odds.get("h2h", {})
        totals_block = match_odds.get("totals", {}).get("totals", {})

        market = {}

        # 1X2 best odds
        best_home = h2h.get("best_home_odds")
        best_draw = h2h.get("best_draw_odds")
        best_away = h2h.get("best_away_odds")
        if best_home or best_draw or best_away:
            market["1x2"] = {
                "home": round(best_home, 2) if best_home else None,
                "draw": round(best_draw, 2) if best_draw else None,
                "away": round(best_away, 2) if best_away else None,
            }

        # Totals -- prefer 2.5 if available, otherwise use whichever
        # line the bookmakers have actually posted (e.g. 3.0, 2.25).
        lines_by_value = {}
        for line_key, line_data in totals_block.items():
            if line_key in ("btts_yes", "btts_no"):
                continue
            lk = line_key.lower()
            try:
                if "_over" in lk:
                    val = float(lk.replace("_over", ""))
                    side = "over"
                elif "_under" in lk:
                    val = float(lk.replace("_under", ""))
                    side = "under"
                else:
                    continue
            except ValueError:
                continue
            lines_by_value.setdefault(val, {})[side] = line_data.get("best_decimal")

        if lines_by_value:
            if 2.5 in lines_by_value:
                chosen_val = 2.5
            else:
                chosen_val = min(lines_by_value.keys(), key=lambda v: abs(v - 2.5))
            chosen = lines_by_value[chosen_val]
            over_v  = chosen.get("over")
            under_v = chosen.get("under")
            if over_v or under_v:
                market["totals"] = {
                    "line":  chosen_val,
                    "over":  round(over_v, 2) if over_v else None,
                    "under": round(under_v, 2) if under_v else None,
                }

        # BTTS
        btts_yes = totals_block.get("btts_yes", {}).get("best_decimal")
        btts_no  = totals_block.get("btts_no", {}).get("best_decimal")
        if btts_yes or btts_no:
            market["btts"] = {
                "yes": round(btts_yes, 2) if btts_yes else None,
                "no":  round(btts_no, 2) if btts_no else None,
            }

        return market
    
    def _find_value_bets(self, pred: dict, match_odds: dict) -> list:
        """Identify bets with model edge above threshold."""
        value_bets = []
        h2h = match_odds.get("h2h", {})
        consensus = h2h.get("consensus", {})
        
        checks = [
            ("Home Win",   pred.get("p_home_win", 0),   consensus.get("home_implied", 0),
             match_odds.get("h2h", {}).get("best_home_odds", 0)),
            
            ("Draw",       pred.get("p_draw", 0),        consensus.get("draw_implied", 0),
             match_odds.get("h2h", {}).get("best_draw_odds", 0)),
            
            ("Away Win",   pred.get("p_away_win", 0),    consensus.get("away_implied", 0),
             match_odds.get("h2h", {}).get("best_away_odds", 0)),
        ]
        
        # Over/Under
        totals = match_odds.get("totals", {}).get("totals", {})
        over_2_5_market = totals.get("2.5_over", totals.get("Over 2.5", {}))
        under_2_5_market = totals.get("2.5_under", totals.get("Under 2.5", {}))
        
        if over_2_5_market:
            checks.append(("Over 2.5", pred.get("p_over_2_5", 0),
                           over_2_5_market.get("avg_implied", 0),
                           over_2_5_market.get("best_decimal", 0)))
        if under_2_5_market:
            checks.append(("Under 2.5", pred.get("p_under_2_5", 0),
                           under_2_5_market.get("avg_implied", 0),
                           under_2_5_market.get("best_decimal", 0)))
        
        # BTTS
        btts_yes = totals.get("btts_yes", {})
        if btts_yes:
            checks.append(("BTTS Yes", pred.get("p_btts", 0),
                           btts_yes.get("avg_implied", 0),
                           btts_yes.get("best_decimal", 0)))
        
        btts_no = totals.get("btts_no", {})
        if btts_no:
            checks.append(("BTTS No", pred.get("p_no_btts", 1 - pred.get("p_btts", 0)),
                           btts_no.get("avg_implied", 0),
                           btts_no.get("best_decimal", 0)))
        
        for label, model_p, market_p, best_odds in checks:
            if not model_p or not best_odds or best_odds <= 1.0:
                continue

            # Edge calculated against best available odds (not consensus avg)
            # This avoids inflating edge by measuring vs average but betting best price
            best_implied = 1 / best_odds
            edge = edge_pct(model_p, best_implied)
            
            if edge >= MIN_EDGE_PCT and edge <= MAX_EDGE_PCT:
                kelly = kelly_fraction(model_p, best_odds) if best_odds else 0
                ev = model_p * (best_odds - 1) - (1 - model_p) if best_odds else 0
                
                if edge >= 10:
                    rating = "\U0001f525 STRONG"
                elif edge >= 6:
                    rating = "\u2705 GOOD"
                else:
                    rating = "\U0001f440 WATCH"
                
                value_bets.append({
                    "market":      label,
                    "model_prob":  round(model_p, 4),
                    "market_prob": round(market_p, 4),
                    "edge_pct":    edge,
                    "best_odds":   best_odds,
                    "kelly_pct":   round(kelly * 100, 2),
                    "ev_per_unit": round(ev, 4),
                    "rating":      rating,
                })
        
        # Sort by edge
        value_bets.sort(key=lambda x: -x["edge_pct"])
        return value_bets
    
    def _confidence_score(self, pred: dict) -> str:
        """Rate prediction confidence based on how decisive the model is."""
        home_p = pred.get("p_home_win", 0.33)
        away_p = pred.get("p_away_win", 0.33)
        max_p  = max(home_p, away_p)
        
        if max_p > 0.60:
            return "HIGH"
        elif max_p > 0.45:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _bet_recommendation(self, value_bets: list) -> str:
        """Top-line bet recommendation."""
        if not value_bets:
            return "No value identified"
        top = value_bets[0]
        return f"{top['rating']} — {top['market']} @ {top['best_odds']} ({top['edge_pct']:+.1f}% edge)"
    
    def run_all_predictions(self, fixtures: list, 
                             odds_data: dict) -> list:
        """Generate predictions for all upcoming fixtures."""
        all_predictions = []
        
        print(f"\n  Generating predictions for {len(fixtures)} fixtures...")
        
        for fixture in fixtures:
            home = fixture.get("home_team")
            away = fixture.get("away_team")
            
            if not home or not away:
                continue
            
            meta = {
                "date":      fixture.get("date"),
                "time":      fixture.get("time"),
                "group":     fixture.get("group", ""),
                "matchday":  fixture.get("matchday"),
                "venue":     fixture.get("venue", ""),
                "fixture_id": fixture.get("fixture_id"),
            }
            
            pred = self.predict_match(
                home, away,
                odds_data=odds_data,
                neutral=True,       # WC matches are at neutral venues
                match_meta=meta,
            )
            
            all_predictions.append(pred)
            
            # Quick summary
            vb = pred["value_bets"]
            vb_str = f"  → {len(vb)} value bet(s)" if vb else "  → no value"
            print(f"  {home} vs {away}: "
                  f"{pred['model']['p_home_win']:.1%}/"
                  f"{pred['model']['p_draw']:.1%}/"
                  f"{pred['model']['p_away_win']:.1%} {vb_str}")

        # Apply daily stake cap across all predictions
        all_predictions = apply_daily_stake_cap(all_predictions)
        return all_predictions


def apply_daily_stake_cap(predictions: list, cap: float = None) -> list:
    """
    Scale down value bet stakes so the total staked per calendar day
    never exceeds DAILY_STAKE_CAP units.

    Strategy: proportional scaling.
      - Collect all value bets grouped by match date.
      - If a day's raw total stake > cap, multiply every bet's kelly by
        (cap / raw_total) so they sum to exactly the cap.
      - kelly_pct_raw  — original quarter-Kelly (always preserved)
      - kelly_pct      — what to actually stake (scaled if cap fired)
      - daily_cap_applied — True when scaling happened

    This runs AFTER run_all_predictions() so per-bet Kelly logic is
    unchanged; we're only trimming the daily aggregate.
    """
    if cap is None:
        cap = DAILY_STAKE_CAP

    # Group predictions by date
    from collections import defaultdict
    by_date = defaultdict(list)
    for pred in predictions:
        date = pred.get("match_meta", {}).get("date", "unknown")
        for bet in pred.get("value_bets", []):
            by_date[date].append(bet)

    for date, bets in by_date.items():
        # kelly_pct is stored as a %, e.g. 5.0 means 5% = 5u per 100u bankroll
        # We treat 1u = 1% of bankroll throughout (MAX_KELLY = 0.05 → 5u)
        raw_total = sum(b["kelly_pct"] for b in bets)

        if raw_total > cap:
            scale = cap / raw_total
            for bet in bets:
                bet["kelly_pct_raw"] = bet["kelly_pct"]
                bet["kelly_pct"]     = round(bet["kelly_pct"] * scale, 2)
                bet["daily_cap_applied"] = True
            print(f"  ⚠ Daily cap fired on {date}: "
                  f"{raw_total:.1f}u → scaled to {cap:.1f}u "
                  f"(×{scale:.3f})")
        else:
            for bet in bets:
                bet["kelly_pct_raw"]     = bet["kelly_pct"]
                bet["daily_cap_applied"] = False

    return predictions


def save_predictions(predictions: list, 
                      path: str = "predictions/latest.json"):
    """Save predictions to JSON. Also writes a dated copy to
    predictions/history/ so the results tracker can find it locally
    (the GitHub history archive is a separate, GitHub-only copy)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    output = {
        "generated_at":     datetime.utcnow().isoformat(),
        "tournament":       "FIFA World Cup 2026",
        "total_fixtures":   len(predictions),
        "total_value_bets": sum(len(p["value_bets"]) for p in predictions),
        "predictions":      predictions,
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n  ✓ Saved {len(predictions)} predictions → {path}")
    
    # Also save a local dated snapshot for results tracking
    history_dir = "predictions/history"
    os.makedirs(history_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    history_path = os.path.join(history_dir, f"{timestamp}.json")
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"  ✓ Saved local history snapshot → {history_path}")
    
    return output


def main():
    """Run full prediction pipeline."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    
    print("\n=== World Cup Prediction Engine ===\n")
    
    # Load model
    model_path = "models/dixon_coles_params.json"
    if not os.path.exists(model_path):
        print("  ✗ No fitted model found. Run models/dixon_coles_model.py first.")
        return
    
    from models.dixon_coles_model import DixonColesModel
    model = DixonColesModel().load(model_path)
    print(f"  ✓ Model loaded ({len(model.teams)} teams)")
    
    # Load Elo
    elo = {}
    elo_path = "data/processed/elo_ratings.json"
    if os.path.exists(elo_path):
        with open(elo_path) as f:
            elo = json.load(f)
    
    # Load fixtures
    fixtures_path = "data/raw/wc2026_fixtures.json"
    if not os.path.exists(fixtures_path):
        print("  ✗ No fixtures found. Run data/fetch_results.py first.")
        return
    
    with open(fixtures_path) as f:
        fixtures = json.load(f)
    
    # Load odds
    odds = {}
    odds_path = "data/raw/odds_latest.json"
    if os.path.exists(odds_path):
        with open(odds_path) as f:
            odds = json.load(f)
        print(f"  ✓ Odds loaded ({len(odds)} matches)")
    else:
        print("  ⚠ No odds data — run data/fetch_odds.py for value bet analysis")
    
    # Run engine
    engine = PredictionEngine(model, elo_ratings=elo)
    predictions = engine.run_all_predictions(fixtures, odds)
    
    # Save
    output = save_predictions(predictions, "predictions/latest.json")
    
    # Summary of best bets
    all_bets = []
    for pred in predictions:
        for bet in pred.get("value_bets", []):
            bet["match"] = f"{pred['home_team']} vs {pred['away_team']}"
            bet["date"]  = pred.get("match_meta", {}).get("date", "")
            all_bets.append(bet)
    
    all_bets.sort(key=lambda x: -x["edge_pct"])
    
    if all_bets:
        print(f"\n{'='*60}")
        print(f"  🏆 TOP VALUE BETS — World Cup 2026")
        print(f"{'='*60}")
        for bet in all_bets[:10]:
            print(f"\n  {bet['match']} ({bet.get('date', '')})")
            print(f"  {bet['rating']} — {bet['market']}")
            print(f"  Odds: {bet['best_odds']} | Model: {bet['model_prob']:.1%} | Market: {bet['market_prob']:.1%}")
            print(f"  Edge: {bet['edge_pct']:+.1f}% | Kelly: {bet['kelly_pct']:.1f}%")
    else:
        print("\n  No value bets found above threshold")
    
    return output


if __name__ == "__main__":
    main()
