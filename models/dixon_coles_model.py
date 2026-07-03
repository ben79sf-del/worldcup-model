"""
dixon_coles_model.py — Bivariate Poisson Goal Model (Optimised)
================================================================
Dixon-Coles (1997) model fitted only on WC-relevant teams.
Significantly faster than fitting all 286 international teams.
"""

import numpy as np
import json
import os
import sys
from scipy.optimize import minimize
from scipy.stats import poisson
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import WC_GROUPS

# All 48 WC 2026 teams — only fit these for speed
WC_TEAMS = [team for teams in WC_GROUPS.values() for team in teams]

# Additional aliases that might appear in historical data
WC_TEAM_ALIASES = {
    "United States":        "USA",
    "Korea Republic":       "South Korea",
    "Czechia":              "Czech Republic",
    "IR Iran":              "Iran",
    "Türkiye":              "Turkey",
    "Bosnia-Herzegovina":   "Bosnia and Herzegovina",
    "DR Congo":             "DR Congo",
    "Côte d'Ivoire":        "Ivory Coast",
    "Cote d'Ivoire":        "Ivory Coast",
    "Congo DR":             "DR Congo",
}

MIN_MATCHES = 5   # Lower threshold so WC teams with less data still get fitted


def dc_correction(home_goals, away_goals, lambda_home, lambda_away, rho):
    if home_goals == 0 and away_goals == 0:
        return 1 - lambda_home * lambda_away * rho
    elif home_goals == 1 and away_goals == 0:
        return 1 + lambda_away * rho
    elif home_goals == 0 and away_goals == 1:
        return 1 + lambda_home * rho
    elif home_goals == 1 and away_goals == 1:
        return 1 - rho
    return 1.0


class DixonColesModel:

    def __init__(self, xi=0.0018):
        self.xi = xi
        self.attack  = {}
        self.defense = {}
        self.home_adv = 0.0
        self.rho = -0.13
        self.mu  = 1.45  # Raised from 1.3 — WC group stage averages ~2.8-2.9 goals/game
        self.fitted = False
        self.teams = []
        self.team_match_counts = {}

    def _time_weight(self, date_str, reference_date="2026-06-11"):
        from datetime import datetime
        try:
            match_dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
            ref_dt   = datetime.strptime(reference_date, "%Y-%m-%d")
            days_ago = (ref_dt - match_dt).days
            return np.exp(-self.xi * max(days_ago, 0))
        except Exception:
            return 0.5

    def _normalize(self, name):
        return WC_TEAM_ALIASES.get(name, name)

    def _expected_goals(self, home, away, neutral=True):
        ha = 0.0 if neutral else self.home_adv
        lh = self.attack.get(home, 1.0) * self.defense.get(away, 1.0) * self.mu * np.exp(ha)
        la = self.attack.get(away, 1.0) * self.defense.get(home, 1.0) * self.mu
        return lh, la

    def _neg_log_likelihood(self, params, matches, teams):
        n = len(teams)
        attack  = dict(zip(teams, params[:n]))
        defense = dict(zip(teams, params[n:2*n]))
        home_adv = params[2*n]
        rho      = params[2*n + 1]

        total_ll = 0.0
        for match in matches:
            home = match["home_team"]
            away = match["away_team"]
            hg   = match["home_goals"]
            ag   = match["away_goals"]
            w    = match.get("_weight", 1.0)
            neutral = match.get("neutral", True)

            if home not in attack or away not in attack:
                continue

            ha = home_adv if not neutral else 0.0
            lh = max(attack[home] * defense[away] * self.mu * np.exp(ha), 0.01)
            la = max(attack[away] * defense[home] * self.mu, 0.01)

            dc = max(dc_correction(hg, ag, lh, la, rho), 1e-6)
            ll = w * (np.log(dc) + np.log(poisson.pmf(hg, lh)) + np.log(poisson.pmf(ag, la)))
            total_ll += ll

        return -total_ll

    def fit(self, matches_df, elo_ratings=None, wc_teams_only=True):
        print("  Fitting Dixon-Coles model...")

        matches = matches_df.copy()

        # Normalize team names
        matches["home_team"] = matches["home_team"].apply(self._normalize)
        matches["away_team"] = matches["away_team"].apply(self._normalize)

        # Filter to WC teams only for speed
        if wc_teams_only:
            wc_set = set(WC_TEAMS)
            matches = matches[
                matches["home_team"].isin(wc_set) |
                matches["away_team"].isin(wc_set)
            ]
            print(f"  Filtered to WC-relevant matches: {len(matches)}")

        # Add time weights
        matches["_weight"] = matches["date"].apply(self._time_weight)

        # Find teams with enough data
        all_teams = pd.concat([matches["home_team"], matches["away_team"]])
        team_counts = all_teams.value_counts()
        valid_teams = team_counts[team_counts >= MIN_MATCHES].index.tolist()

        # Prioritise WC teams — include even with fewer matches
        wc_in_data = [t for t in WC_TEAMS if t in team_counts.index]
        valid_teams = wc_in_data  # Strictly WC teams only

        matches = matches[
            matches["home_team"].isin(valid_teams) &
            matches["away_team"].isin(valid_teams)
        ]

        self.teams = sorted(valid_teams)
        n = len(self.teams)
        print(f"  Teams being fitted: {n}")
        print(f"  Training matches:   {len(matches)}")

        # Track per-team sample size for confidence blending
        self.team_match_counts = team_counts.to_dict()

        match_records = matches.to_dict("records")

        # Initialise from Elo
        if elo_ratings:
            avg_elo = np.mean(list(elo_ratings.values()))
            init_attack  = [elo_ratings.get(t, avg_elo) / avg_elo for t in self.teams]
            init_defense = [avg_elo / max(elo_ratings.get(t, avg_elo), 1) for t in self.teams]
        else:
            init_attack  = [1.0] * n
            init_defense = [1.0] * n

        x0 = np.array(init_attack + init_defense + [0.1, -0.13])
        bounds = [(0.1, 5.0)] * n + [(0.1, 5.0)] * n + [(-0.5, 0.5)] + [(-0.5, 0.0)]

        print("  Optimising (may take 1-3 mins for WC teams)...")
        result = minimize(
            self._neg_log_likelihood,
            x0,
            args=(match_records, self.teams),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 500, "ftol": 1e-7}
        )

        if result.success:
            print(f"  ✓ Converged in {result.nit} iterations")
        else:
            print(f"  ⚠ Did not fully converge: {result.message[:60]}")

        opt = result.x
        raw_attack  = dict(zip(self.teams, opt[:n]))
        raw_defense = dict(zip(self.teams, opt[n:2*n]))

        avg_atk = sum(raw_attack.values()) / len(raw_attack)
        self.attack  = {t: v / avg_atk for t, v in raw_attack.items()}
        self.defense = raw_defense
        self.home_adv = opt[2*n]
        self.rho      = opt[2*n + 1]
        self.fitted   = True

        print(f"  Home advantage: {np.exp(self.home_adv):.3f}x")
        print(f"  Rho: {self.rho:.3f}")
        return self

    def predict_score_matrix(self, home, away, neutral=True, max_goals=8):
        lh, la = self._expected_goals(home, away, neutral)
        matrix = np.zeros((max_goals + 1, max_goals + 1))
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                dc = dc_correction(i, j, lh, la, self.rho)
                matrix[i, j] = max(dc * poisson.pmf(i, lh) * poisson.pmf(j, la), 0)
        matrix /= matrix.sum()
        return matrix

    def _confidence_weight(self, home, away, full_data_threshold=40):
        """
        Returns 0.0-1.0: how much to trust the Dixon-Coles prediction
        vs Elo. Based on the team with the SMALLER sample size.
        Raised threshold to 40 — DC estimates aren't reliable below this.
        """
        n_home = self.team_match_counts.get(home, 0)
        n_away = self.team_match_counts.get(away, 0)
        n_min  = min(n_home, n_away)

        if n_min >= full_data_threshold:
            return 1.0
        if n_min <= 0:
            return 0.0
        return n_min / full_data_threshold

    def _elo_prediction(self, home, away, elo_ratings, neutral=True):
        """Get Elo-based win/draw/loss + xG estimate."""
        from data.fetch_elo import get_elo_win_probability
        elo_h = elo_ratings.get(home, 1700)
        elo_a = elo_ratings.get(away, 1700)
        ph, pd_, pa = get_elo_win_probability(elo_h, elo_a, neutral=neutral)

        # Derive xG from Elo gap: stronger team gets more goals,
        # weaker team's goals shrink as the gap widens
        elo_diff = elo_h - elo_a + (0 if neutral else 65)
        base_total = 2.9  # WC group stage average total goals

        # Logistic scaling: large gaps -> lopsided goal split
        strength_ratio = 1 / (1 + 10 ** (-elo_diff / 400))  # 0-1
        lh = base_total * strength_ratio
        la = base_total * (1 - strength_ratio)

        # Floor so a team never has near-zero expected goals
        lh = max(lh, 0.35)
        la = max(la, 0.35)

        return ph, pd_, pa, lh, la

    def predict_match(self, home, away, neutral=True, elo_ratings=None):
        home = self._normalize(home)
        away = self._normalize(away)

        use_fallback = (home not in self.attack or away not in self.attack or not self.fitted)

        if use_fallback and elo_ratings:
            ph, pd_, pa, lh, la = self._elo_prediction(home, away, elo_ratings, neutral)
            source = "elo_fallback"
        elif use_fallback:
            ph, pd_, pa = 0.333, 0.333, 0.334
            lh = la = 1.3
            source = "uniform_fallback"
        else:
            matrix = self.predict_score_matrix(home, away, neutral)
            lh_dc, la_dc = self._expected_goals(home, away, neutral)
            ph_dc  = float(np.sum(np.tril(matrix, -1)))
            pd_dc  = float(np.sum(np.diag(matrix)))
            pa_dc  = float(np.sum(np.triu(matrix, 1)))

            # ── Confidence blend with Elo ─────────────────────────────────
            # Low-sample teams (e.g. Curacao, Haiti) get pulled toward Elo,
            # which correctly captures the gap vs strong teams even without
            # enough goal-data to fit attack/defense reliably.
            conf = self._confidence_weight(home, away)

            if elo_ratings and conf < 1.0:
                ph_elo, pd_elo, pa_elo, lh_elo, la_elo = self._elo_prediction(
                    home, away, elo_ratings, neutral
                )
                ph = conf * ph_dc + (1 - conf) * ph_elo
                pd_ = conf * pd_dc + (1 - conf) * pd_elo
                pa = conf * pa_dc + (1 - conf) * pa_elo
                lh = conf * lh_dc + (1 - conf) * lh_elo
                la = conf * la_dc + (1 - conf) * la_elo

                # Renormalise probabilities to sum to 1
                total_p = ph + pd_ + pa
                ph, pd_, pa = ph / total_p, pd_ / total_p, pa / total_p

                source = "dixon_coles" if conf >= 0.99 else f"blended_{conf:.0%}"
            else:
                ph, pd_, pa, lh, la = ph_dc, pd_dc, pa_dc, lh_dc, la_dc
                source = "dixon_coles"

        result = {
            "home_team": home, "away_team": away, "neutral": neutral,
            "lambda_home": round(lh, 4), "lambda_away": round(la, 4),
            "expected_total": round(lh + la, 4),
            "p_home_win": round(ph, 4), "p_draw": round(pd_, 4), "p_away_win": round(pa, 4),
            "data_source": source,
        }

        if source == "dixon_coles" or source.startswith("blended"):
            if source == "dixon_coles":
                matrix = self.predict_score_matrix(home, away, neutral)
            else:
                # Build a fresh Poisson matrix from the blended lambdas
                matrix = np.zeros((9, 9))
                for i in range(9):
                    for j in range(9):
                        dc = dc_correction(i, j, lh, la, self.rho)
                        matrix[i, j] = max(dc * poisson.pmf(i, lh) * poisson.pmf(j, la), 0)
                matrix /= matrix.sum()

            totals = np.zeros(16)
            for i in range(matrix.shape[0]):
                for j in range(matrix.shape[1]):
                    if i + j < 16:
                        totals[i + j] += matrix[i, j]

            result["p_over_0_5"]  = float(1 - totals[0])
            result["p_over_1_5"]  = float(1 - totals[0] - totals[1])
            result["p_over_2_5"]  = float(sum(totals[3:]))
            result["p_over_3_5"]  = float(sum(totals[4:]))
            result["p_over_4_5"]  = float(sum(totals[5:]))
            result["p_under_2_5"] = float(1 - result["p_over_2_5"])
            result["p_under_3_5"] = float(1 - result["p_over_3_5"])
            result["p_btts"]      = round((1 - poisson.pmf(0, lh)) * (1 - poisson.pmf(0, la)), 4)
            result["p_no_btts"]   = round(1 - result["p_btts"], 4)
            result["asian_handicap"] = self._asian_handicap_probs(matrix)

            flat = [(matrix[i,j], f"{i}-{j}") for i in range(matrix.shape[0]) for j in range(matrix.shape[1])]
            flat.sort(reverse=True)
            result["most_likely_score"] = flat[0][1]
            result["top_scorelines"] = [{"score": s, "probability": round(p, 4)} for p, s in flat[:6]]
        else:
            result["p_over_2_5"]  = round(1 - poisson.cdf(2, lh + la), 4)
            result["p_under_2_5"] = round(1 - result["p_over_2_5"], 4)
            result["p_btts"]      = round((1 - poisson.pmf(0, lh)) * (1 - poisson.pmf(0, la)), 4)
            result["p_no_btts"]   = round(1 - result["p_btts"], 4)

        return result

    def _asian_handicap_probs(self, matrix):
        results = {}
        for line in [-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5]:
            ph = pd_ = pa = 0.0
            for i in range(matrix.shape[0]):
                for j in range(matrix.shape[1]):
                    gd = (i - j) + line
                    if gd > 0:   ph += matrix[i, j]
                    elif gd == 0: pd_ += matrix[i, j]
                    else:         pa += matrix[i, j]
            results[f"home_{line:+.1f}"] = {
                "home_cover": round(ph, 4), "push": round(pd_, 4), "away_cover": round(pa, 4)
            }
        return results

    def save(self, path="models/dixon_coles_params.json"):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "attack": self.attack, "defense": self.defense,
                "home_adv": self.home_adv, "rho": self.rho,
                "mu": self.mu, "xi": self.xi,
                "teams": self.teams, "fitted": self.fitted,
                "team_match_counts": self.team_match_counts,
            }, f, indent=2)
        print(f"  ✓ Model saved → {path}")

    def load(self, path="models/dixon_coles_params.json"):
        with open(path) as f:
            p = json.load(f)
        self.attack = p["attack"]; self.defense = p["defense"]
        self.home_adv = p["home_adv"]; self.rho = p["rho"]
        self.mu = p.get("mu", 1.45)  # Default to 1.45 if not in saved params
        self.xi = p["xi"]
        self.teams = p["teams"]; self.fitted = p["fitted"]
        self.team_match_counts = p.get("team_match_counts", {})
        return self

    def print_team_ratings(self, n=20):
        if not self.attack:
            print("  Model not fitted."); return
        sorted_teams = sorted(self.attack.items(), key=lambda x: -x[1])[:n]
        print(f"\n  {'Team':<30} {'Attack':>8} {'Defense':>8}")
        print("  " + "-" * 48)
        for team, atk in sorted_teams:
            print(f"  {team:<30} {atk:>8.3f} {self.defense.get(team, 1.0):>8.3f}")


def main():
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    os.makedirs("models", exist_ok=True)

    print("\n=== Dixon-Coles Model Training ===\n")

    hist_path = "data/raw/historical_matches.csv"
    if not os.path.exists(hist_path):
        print("  ✗ No historical data. Run data/fetch_results.py first.")
        return None

    df = pd.read_csv(hist_path)
    print(f"  Loaded {len(df)} historical matches")

    elo = {}
    elo_path = "data/processed/elo_ratings.json"
    if os.path.exists(elo_path):
        with open(elo_path) as f:
            elo = json.load(f)
        print(f"  Loaded Elo for {len(elo)} teams")

    model = DixonColesModel(xi=0.0018)
    model.fit(df, elo_ratings=elo, wc_teams_only=True)
    model.print_team_ratings(30)
    model.save("models/dixon_coles_params.json")

    print("\n  Sample predictions:")
    test_matches = [
        ("Argentina", "Algeria"), ("France", "Senegal"),
        ("Spain", "Morocco"), ("England", "Nigeria"),
        ("Germany", "Japan"), ("Brazil", "Ecuador"),
        ("Mexico", "South Africa"), ("USA", "Paraguay"),
    ]
    for home, away in test_matches:
        pred = model.predict_match(home, away, neutral=True, elo_ratings=elo)
        src = "DC" if pred["data_source"] == "dixon_coles" else "Elo"
        print(f"  [{src}] {home} vs {away}: "
              f"{pred['p_home_win']:.1%}/{pred['p_draw']:.1%}/{pred['p_away_win']:.1%}  "
              f"xG {pred['lambda_home']:.2f}-{pred['lambda_away']:.2f}  "
              f"O2.5 {pred.get('p_over_2_5',0):.1%}")

    return model


if __name__ == "__main__":
    model = main()
    print("\n✅ Dixon-Coles model training complete")
