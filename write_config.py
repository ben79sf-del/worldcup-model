"""
write_config.py - Called by GitHub Actions to write config/config.py from environment variables
"""
import os

odds_key = os.environ.get('ODDS_API_KEY', '')
fd_key = os.environ.get('FOOTBALL_DATA_KEY', '')
gh_token = os.environ.get('GH_TOKEN', '')

print(f"Writing config (token length: {len(gh_token)}, odds key length: {len(odds_key)})")

config = f'''
ODDS_API_KEY = "{odds_key}"
FOOTBALL_DATA_KEY = "{fd_key}"
ODDS_BASE_URL = "https://api.the-odds-api.com/v4"
ODDS_SPORT = "soccer_fifa_world_cup"
ODDS_REGIONS = "us,uk,eu,au"
ODDS_MARKETS = "h2h,spreads,totals"
ODDS_BOOKMAKERS = "pinnacle,bet365,draftkings,fanduel,betmgm"
FD_BASE_URL = "https://api.football-data.org/v4"
FD_COMPETITION_WC = "WC"
FD_COMPETITION_EC = "EC"
FD_COMPETITION_CL = "CL"
CLUBELO_BASE_URL = "http://api.clubelo.com"
MIN_EDGE_PCT = 6.0
MAX_EDGE_PCT = 30.0
KELLY_FRACTION = 0.25
MAX_KELLY = 0.05
DAILY_STAKE_CAP = 20.0
FORM_WINDOW = 15
FORM_WEIGHTS = {{"WC":1.0,"WCQ":0.9,"EURO":0.85,"COPA":0.85,"NL":0.75,"FRIENDLY":0.1}}
GITHUB_TOKEN = "{gh_token}"
GITHUB_REPO = "ben79sf-del/worldcup-model"
GITHUB_BRANCH = "main"
PREDICTIONS_PATH = "predictions/latest.json"
HISTORY_PATH = "predictions/history.json"
WC_GROUPS = {{"A":["Mexico","South Africa","South Korea","Czechia"],"B":["Canada","Bosnia and Herzegovina","Qatar","Switzerland"],"C":["Germany","Japan","Chile","Saudi Arabia"],"D":["USA","Paraguay","Australia","Turkey"],"E":["Spain","Morocco","Venezuela","Kenya"],"F":["France","Mali","Egypt","Uruguay"],"G":["Belgium","Egypt","Iran","New Zealand"],"H":["Portugal","Senegal","Indonesia","Serbia"],"I":["England","Slovakia","Nigeria","Trinidad and Tobago"],"J":["Argentina","Algeria","Austria","Jordan"],"K":["Portugal","DR Congo","Uzbekistan","Colombia"],"L":["Brazil","Ecuador","Ivory Coast","Hungary"]}}
TEAM_ALIASES = {{"United States":"USA","Bosnia & Herzegovina":"Bosnia and Herzegovina","Czechia":"Czech Republic","DR Congo":"Congo DR","Cape Verde Islands":"Cape Verde"}}
DATA_DIR = "data/raw"
PROCESSED_DIR = "data/processed"
PREDICTIONS_DIR = "predictions"
DASHBOARD_DIR = "dashboard"
'''

os.makedirs('config', exist_ok=True)
with open('config/config.py', 'w') as f:
    f.write(config)

print("config/config.py written OK")
