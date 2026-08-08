#!/usr/bin/env python3
"""
Fetches MLB box scores for a date range, computes a custom "small ball"
score per roster player, and writes data/scores.json.

Scoring:
  +1  Single, Double, Stolen Base, Hit By Pitch, Sac Bunt, Sac Fly
  -1  Home Run, Caught Stealing, Walk (incl. intentional), Strikeout,
      Ground Into Double Play
  Triples and runs/RBI are not scored.

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
SEASON = 2026  # used for the AVG tiebreaker lookup


def fetch_json(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            with urlopen(url, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except URLError as e:
            if attempt == retries - 1:
                raise
            print(f"  retrying ({e})...", file=sys.stderr)
            time.sleep(delay)


def get_game_ids(start_date, end_date):
    url = f"{BASE_URL}/schedule?sportId=1&startDate={start_date}&endDate={end_date}"
    data = fetch_json(url)
    game_ids = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            # Only count completed games so partial stats aren't double counted
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
    """Compute the custom score from a single game's batting stat line."""
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

    score = (
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

    return score, {
        "singles": singles,
        "doubles": doubles,
        "triples": triples,
        "home_runs": home_runs,
        "walks": walks,
        "hbp": hbp,
        "sac_bunts": sac_bunts,
        "sac_flies": sac_flies,
        "strikeouts": strikeouts,
        "stolen_bases": stolen_bases,
        "caught_stealing": caught_stealing,
        "gidp": gidp,
    }


def get_season_avg(person_id):
    url = (
        f"{BASE_URL}/people/{person_id}/stats"
        f"?stats=season&group=hitting&season={SEASON}"
    )
    try:
        data = fetch_json(url)
        splits = data.get("stats", [{}])[0].get("splits", [])
        if splits:
            return float(splits[0]["stat"].get("avg", ".000"))
    except Exception as e:
        print(f"  could not fetch AVG for {person_id}: {e}", file=sys.stderr)
    return 0.0


def last_name(full_name):
    return full_name.strip().split(" ")[-1]


def main():
    roster_path = ROOT / "roster.json"
    roster = json.loads(roster_path.read_text())
    start_date, end_date = roster["startDate"], roster["endDate"]
    players = roster["players"]
    roster_ids = {p["id"] for p in players}

    print(f"Fetching games {start_date} to {end_date}...")
    game_ids = get_game_ids(start_date, end_date)
    print(f"Found {len(game_ids)} completed games.")

    totals = {p["id"]: {"score": 0, "breakdown_total": {}} for p in players}

    for i, game_id in enumerate(game_ids, 1):
        print(f"  [{i}/{len(game_ids)}] game {game_id}")
        lines = get_boxscore_stat_lines(game_id)
        for pid in roster_ids:
            if pid in lines:
                score, breakdown = compute_score(lines[pid])
                totals[pid]["score"] += score
                for k, v in breakdown.items():
                    totals[pid]["breakdown_total"][k] = (
                        totals[pid]["breakdown_total"].get(k, 0) + v
                    )

    leaderboard = []
    for p in players:
        pid = p["id"]
        avg = get_season_avg(pid)
        leaderboard.append(
            {
                "id": pid,
                "name": p["name"],
                "team": p.get("team"),
                "score": totals[pid]["score"],
                "avg": avg,
                "breakdown": totals[pid]["breakdown_total"],
            }
        )

    # Sort: score desc, then AVG desc, then last name asc
    leaderboard.sort(key=lambda p: (-p["score"], -p["avg"], last_name(p["name"])))

    output = {
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "startDate": start_date,
        "endDate": end_date,
        "leaderboard": leaderboard,
    }

    out_path = ROOT / "data" / "scores.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
