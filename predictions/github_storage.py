"""
github_storage.py — Push predictions to GitHub
===============================================
Mirrors your Tennis/MLB model pattern.
Stores latest predictions + rolling history in your repo.
"""

import json
import base64
import requests
import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config.config import GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH


GITHUB_API = "https://api.github.com"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept":        "application/vnd.github.v3+json",
    "Content-Type":  "application/json",
}


def get_file_sha(path: str) -> str | None:
    """Get current SHA of a file (needed for updates)."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    params = {"ref": GITHUB_BRANCH}
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    if r.status_code == 200:
        return r.json().get("sha")
    return None


def push_file(path: str, content: dict | list, 
              message: str = None) -> bool:
    """Push JSON content to GitHub repo."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}"
    
    content_str    = json.dumps(content, indent=2)
    content_b64    = base64.b64encode(content_str.encode()).decode()
    commit_message = message or f"Update {path} — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    
    sha = get_file_sha(path)
    
    payload = {
        "message": commit_message,
        "content": content_b64,
        "branch":  GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha
    
    try:
        r = requests.put(url, headers=HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        action = "Updated" if sha else "Created"
        print(f"  ✓ GitHub: {action} {path}")
        return True
    except Exception as e:
        print(f"  ✗ GitHub push failed for {path}: {e}")
        return False


def push_predictions(predictions_output: dict) -> bool:
    """Push latest predictions + append to history."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Push latest
    success = push_file(
        "predictions/latest.json",
        predictions_output,
        f"WC predictions update — {timestamp}"
    )
    
    # Append to daily history
    history_path = f"predictions/history/{timestamp}.json"
    push_file(history_path, predictions_output, f"WC daily archive — {timestamp}")
    
    # Update value_bets summary (easy reading)
    all_bets = []
    for pred in predictions_output.get("predictions", []):
        for bet in pred.get("value_bets", []):
            all_bets.append({
                "match":        f"{pred['home_team']} vs {pred['away_team']}",
                "date":         pred.get("match_meta", {}).get("date", ""),
                "group":        pred.get("match_meta", {}).get("group", ""),
                "market":       bet["market"],
                "edge_pct":     bet["edge_pct"],
                "model_prob":   bet["model_prob"],
                "market_prob":  bet["market_prob"],
                "best_odds":    bet["best_odds"],
                "kelly_pct":    bet["kelly_pct"],
                "rating":       bet["rating"],
            })
    
    all_bets.sort(key=lambda x: -x["edge_pct"])
    
    push_file(
        "predictions/value_bets_today.json",
        {
            "date":       timestamp,
            "generated":  predictions_output.get("generated_at"),
            "count":      len(all_bets),
            "value_bets": all_bets,
        },
        f"WC value bets — {timestamp}"
    )
    
    return success


def push_results_log(results_log: dict) -> bool:
    """Push results tracking log to GitHub."""
    timestamp = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
    return push_file(
        "predictions/results_log.json",
        results_log,
        f"WC results tracking update — {timestamp}"
    )


def fetch_predictions_from_github() -> dict:
    """Pull latest predictions back from GitHub (for dashboard)."""
    url = f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/predictions/latest.json"
    params = {"ref": GITHUB_BRANCH}
    
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=15)
        r.raise_for_status()
        content_b64 = r.json().get("content", "")
        content_str = base64.b64decode(content_b64).decode()
        return json.loads(content_str)
    except Exception as e:
        print(f"  ✗ Failed to fetch from GitHub: {e}")
        return {}


if __name__ == "__main__":
    # Test connection
    print("Testing GitHub connection...")
    sha = get_file_sha("README.md")
    if sha:
        print(f"  ✓ Connected to {GITHUB_REPO}")
    else:
        print(f"  ✗ Could not connect — check GITHUB_TOKEN and GITHUB_REPO")
