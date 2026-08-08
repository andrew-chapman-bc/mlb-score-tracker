# Small Ball Score Tracker

A leaderboard that scores MLB players on contact/speed events instead of
power:

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

- `roster.json` — the players you're tracking, plus the date range. Edit
  this file to add/remove players or change dates; no code changes needed.
- `fetch_scores.py` — pulls completed games in the date range from the
  [MLB Stats API](https://statsapi.mlb.com) (free, no key needed), computes
  each roster player's score, and writes `data/scores.json`.
- `.github/workflows/update-scores.yml` — runs the script once a day and
  commits the updated `data/scores.json` automatically.
- `index.html` — static leaderboard page that reads `data/scores.json`.
  Includes a search box to filter by player/team.

## Setup

1. Create a new GitHub repo and push this folder to it.
2. In the repo settings, enable **GitHub Pages** → Deploy from branch →
   `main` → `/ (root)`.
3. In the repo's **Actions** tab, confirm workflows are enabled. The
   `Update Scores` workflow runs daily at 09:00 UTC, or trigger it manually
   from the Actions tab (**Run workflow**) any time.
4. Edit `roster.json` with your friends' actual player picks (find a
   player's MLB ID from their `mlb.com/player/...` URL).
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
  the player's current season stats, not restricted to the date range.
- If MLB Stats API is briefly unavailable, the script retries a few times
  before failing; a failed Action run just leaves yesterday's data in place.
