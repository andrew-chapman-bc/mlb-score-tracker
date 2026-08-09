# Small Ball Score Tracker

A leaderboard that scores MLB players on contact/speed events instead of
power. This was a fun game some friends of mine came up with for a
way to determine our fantasy football draft order. I wanted to create
a website people could use to live track each day how their players 
were doing. Code created with the assistance of Claude Sonnet:

| Event | Points |
|---|---|
| Single | +1 |
| Double | +1 |
| Stolen Base | +1 |
| Hit By Pitch | +1 |
| Sac Bunt | +1 |
| Sac Fly | +1 |
| Home Run | -1 |
| Caught Stealing | -1 |
| Walk (incl. intentional) | -1 |
| Strikeout | -1 |
| Grounded Into Double Play | -1 |

Triples, runs, and RBI are not scored. Ties break on season batting average
(higher wins), then alphabetically by last name.

## How it works

- `fetch_scores.py` — pulls every active player in the league (excluding
  pitchers by default), pulls completed games in the date range from the
  [MLB Stats API](https://statsapi.mlb.com) (free, no key needed), computes
  each player's score, and writes `data/scores.json`. The date range and
  the `EXCLUDE_PITCHERS` flag are set as constants near the top of the file.
- `.github/workflows/update-scores.yml` — runs the script once a day and
  commits the updated `data/scores.json` automatically.
- `index.html` — static leaderboard page that reads `data/scores.json`.
  Includes a search box (filters by player/team) and pagination at 25
  players per page.

## Setup

1. Create a new GitHub repo and push this folder to it.
2. In the repo settings, enable **GitHub Pages** → Deploy from branch →
   `main` → `/ (root)`.
3. In the repo's **Actions** tab, confirm workflows are enabled. The
   `Update Scores` workflow runs daily at 09:00 UTC, or trigger it manually
   from the Actions tab (**Run workflow**) any time.
4. Edit the `START_DATE` / `END_DATE` constants at the top of
   `fetch_scores.py` if you want a different window.
5. Visit `https://<your-username>.github.io/<repo-name>/`.

## Running locally

```bash
python fetch_scores.py   # writes data/scores.json
python -m http.server     # then open http://localhost:8000
```

No dependencies beyond Python 3's standard library.

## Notes / known limitations

- Only fully completed games (`codedGameState == "F"`) are counted, so
  in-progress games aren't double-counted across daily runs.
- Season AVG (used only as a tiebreaker) is pulled live at fetch time from
  the player's current season stats, not restricted to the date range, and
  fetched in bulk (a couple of API calls) rather than per-player.
- Every active player in the league is included, even those who didn't
  play in the date range (they show up with a score of 0). Pitchers are
  excluded by default (`EXCLUDE_PITCHERS = True` in `fetch_scores.py`) —
  set it to `False` to include them.
- With ~750-800 players in the file, `data/scores.json` stays well under
  a size that's a problem for a static fetch; pagination happens entirely
  client-side in the browser, so there's no backend to scale.
- If MLB Stats API is briefly unavailable, the script retries a few times
  before failing; a failed Action run just leaves yesterday's data in place.
- The exact query parameters for the bulk stats endpoint
  (`/api/v1/stats?stats=season&group=hitting...`) haven't been verified
  against a live call in this environment (no network access here) — worth
  a manual test run before relying on the daily cron.
