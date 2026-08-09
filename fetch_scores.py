#!/usr/bin/env python3
"""
Fetches MLB box scores for a date range and computes a custom "small ball"
score for every active position player in the league, writing
data/scores.json.

Scoring:
  +1  Single, Double, Stolen Base, Hit By Pitch, Sac Bunt, Sac Fly
  -1  Home Run, Caught Stealing, Walk (incl. intentional), Strikeout,
      Ground Into Double Play

Data source: MLB Stats API (statsapi.mlb.com) - free, no key required.
"""

import json
import sys
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

BASE_URL = "https://statsapi.mlb.com/api/v1"
ROOT = Path(__file__).parent
SEASON = 2026

# Date range for this run. Edit these two lines to change the window.
START_DATE = "2026-08-09"
END_DATE = "2026-08-16"

# Exclude true pitchers from the board (position players + two-way players
# like Ohtani still show up since their primary position isn't "P").
EXCLUDE_PITCHERS = True


def fetch_json(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            with urlopen(url, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except URLError as e:
            if attempt == retries - 1:
                raise
            print(f"  retrying ({e})...", file=sys.stderr)
            time.sleep(delay)


def get_team_abbreviations():
    """Map team id -> abbreviation, e.g. 147 -> 'NYY'."""
    data = fetch_json(f"{BASE_URL}/teams?sportId=1")
    return {t["id"]: t.get("abbreviation", "") for t in data.get("teams", [])}


def get_all_players(season):
    """All players (any roster status) tagged to the given season."""
    data = fetch_json(f"{BASE_URL}/sports/1/players?season={season}")
    players = {}
    for p in data.get("people", []):
        pid = p.get("id")
        if not pid:
            continue
        pos_code = p.get("primaryPosition", {}).get("code")
        if EXCLUDE_PITCHERS and pos_code == "1":
            continue
        players[pid] = {
            "id": pid,
            "name": p.get("fullName", "Unknown"),
            "team_id": p.get("currentTeam", {}).get("id"),
        }
    return players


def get_season_avg_map(season):
    """id -> AVG for the season, fetched in bulk rather than per-player."""
    avg_map = {}
    offset = 0
    limit = 500
    while True:
        url = (
            f"{BASE_URL}/stats?stats=season&group=hitting&sportId=1"
            f"&season={season}&limit={limit}&offset={offset}"
        )
        data = fetch_json(url)
        splits = data.get("stats", [{}])[0].get("splits", [])
        if not splits:
            break
        for s in splits:
            pid = s.get("player", {}).get("id")
            avg = s.get("stat", {}).get("avg")
            if pid and avg is not None:
                try:
                    avg_map[pid] = float(avg)
                except ValueError:
                    avg_map[pid] = 0.0
        if len(splits) < limit:
            break
        offset += limit
    return avg_map


def get_game_ids(start_date, end_date):
    url = f"{BASE_URL}/schedule?sportId=1&startDate={start_date}&endDate={end_date}"
    data = fetch_json(url)
    game_ids = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            if game.get("status", {}).get("codedGameState") == "F":
                game_ids.append(game["gamePk"])
    return game_ids


def get_boxscore_stat_lines(game_id):
    """Returns {mlb_person_id: batting_stat_dict} for all players in a game."""
    url = f"{BASE_URL}/game/{game_id}/boxscore"
    data = fetch_json(url)
    lines = {}
    for side in ("home", "away"):
        players = data.get("teams", {}).get(side, {}).get("players", {})
        for _, pdata in players.items():
            person_id = pdata.get("person", {}).get("id")
            batting = pdata.get("stats", {}).get("batting", {})
            if person_id and batting:
                lines[person_id] = batting
    return lines


def compute_score(batting):
    hits = batting.get("hits", 0)
    doubles = batting.get("doubles", 0)
    triples = batting.get("triples", 0)
    home_runs = batting.get("homeRuns", 0)
    singles = hits - doubles - triples - home_runs

    walks = batting.get("baseOnBalls", 0)  # already includes intentional walks
    hbp = batting.get("hitByPitch", 0)
    sac_bunts = batting.get("sacBunts", 0)
    sac_flies = batting.get("sacFlies", 0)
    strikeouts = batting.get("strikeOuts", 0)
    stolen_bases = batting.get("stolenBases", 0)
    caught_stealing = batting.get("caughtStealing", 0)
    gidp = batting.get("groundIntoDoublePlay", 0)

    return (
        singles
        + doubles
        + stolen_bases
        + hbp
        + sac_bunts
        + sac_flies
        - home_runs
        - caught_stealing
        - walks
        - strikeouts
        - gidp
    )


def last_name(full_name):
    return full_name.strip().split(" ")[-1]


def main():
    print("Fetching team list...")
    team_abbrevs = get_team_abbreviations()

    print("Fetching full player list...")
    all_players = get_all_players(SEASON)
    print(f"  {len(all_players)} players in scope.")

    print("Fetching season AVG for all players (bulk)...")
    avg_map = get_season_avg_map(SEASON)

    print(f"Fetching games {START_DATE} to {END_DATE}...")
    game_ids = get_game_ids(START_DATE, END_DATE)
    print(f"  {len(game_ids)} completed games.")

    # Aggregate scores for every batter encountered in the range, keyed by id.
    # No need to check against a fixed roster -- we score whoever played.
    score_totals = {}
    for i, game_id in enumerate(game_ids, 1):
        print(f"  [{i}/{len(game_ids)}] game {game_id}")
        lines = get_boxscore_stat_lines(game_id)
        for pid, batting in lines.items():
            score_totals[pid] = score_totals.get(pid, 0) + compute_score(batting)

    leaderboard = []
    for pid, info in all_players.items():
        leaderboard.append(
            {
                "id": pid,
                "name": info["name"],
                "team": team_abbrevs.get(info["team_id"], None),
                "score": score_totals.get(pid, 0),
                "avg": avg_map.get(pid, 0.0),
            }
        )

    # Sort: score desc, then AVG desc, then last name asc
    leaderboard.sort(key=lambda p: (-p["score"], -p["avg"], last_name(p["name"])))

    output = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "startDate": START_DATE,
        "endDate": END_DATE,
        "leaderboard": leaderboard,
    }

    out_path = ROOT / "data" / "scores.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {out_path} ({len(leaderboard)} players)")


if __name__ == "__main__":
    main()
