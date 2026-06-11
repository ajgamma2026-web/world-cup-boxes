import os
import requests

API_KEY = os.environ.get("ODDS_API_KEY", "9d2f7dbad04e89a62bf9fa5973d0a991")
BASE_URL = "https://api.the-odds-api.com/v4/sports"

SPORT = "soccer_fifa_world_cup"
REGIONS = "us"
MARKETS = "h2h"
ODDS_FORMAT = "decimal"


def fetch_odds():
    url = f"{BASE_URL}/{SPORT}/odds"
    params = {
        "apiKey": API_KEY,
        "regions": REGIONS,
        "markets": MARKETS,
        "oddsFormat": ODDS_FORMAT,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


def find_game(games, team1="Mexico", team2="South Africa"):
    t1, t2 = team1.lower(), team2.lower()
    for game in games:
        home = game.get("home_team", "").lower()
        away = game.get("away_team", "").lower()
        if (t1 in home or t1 in away) and (t2 in home or t2 in away):
            return game
    return None


def decimal_to_implied_prob(decimal_odds):
    return 1 / decimal_odds


def get_best_odds(game):
    """Average implied probs across all bookmakers for each outcome."""
    outcome_probs = {}
    outcome_counts = {}

    for bookmaker in game.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market["key"] != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                name = outcome["name"]
                prob = decimal_to_implied_prob(outcome["price"])
                outcome_probs[name] = outcome_probs.get(name, 0) + prob
                outcome_counts[name] = outcome_counts.get(name, 0) + 1

    return {name: outcome_probs[name] / outcome_counts[name] for name in outcome_probs}


def normalize(probs):
    total = sum(probs.values())
    return {name: p / total for name, p in probs.items()}


def assign_dollars(normalized, total=100):
    """Round to nearest dollar, then fix rounding error on the largest value."""
    dollars = {name: round(p * total) for name, p in normalized.items()}
    diff = total - sum(dollars.values())
    if diff != 0:
        # Apply correction to the outcome with the largest raw value
        largest = max(normalized, key=normalized.get)
        dollars[largest] += diff
    return dollars


def main():
    print("Fetching odds...\n")
    games = fetch_odds()

    game = find_game(games)
    if not game:
        print("Mexico vs South Africa game not found. Available games:")
        for g in games:
            print(f"  {g['home_team']} vs {g['away_team']} ({g['commence_time']})")
        return

    print(f"Found: {game['home_team']} vs {game['away_team']}")
    print(f"Start time: {game['commence_time']}\n")

    raw_probs = get_best_odds(game)

    if len(raw_probs) != 3:
        print(f"Expected 3 outcomes (home/draw/away), got: {list(raw_probs.keys())}")
        return

    normalized = normalize(raw_probs)
    dollars = assign_dollars(normalized)

    print(f"{'Outcome':<20} {'Raw Prob':>10} {'Normalized':>12} {'$Value':>8}")
    print("-" * 54)
    for name in raw_probs:
        raw_pct = raw_probs[name] * 100
        norm_pct = normalized[name] * 100
        print(f"{name:<20} {raw_pct:>9.2f}%  {norm_pct:>10.2f}%  ${dollars[name]:>6}")

    print("-" * 54)
    print(f"{'TOTAL':<20} {'':>10} {100.00:>10.2f}%  ${sum(dollars.values()):>6}")


if __name__ == "__main__":
    main()
