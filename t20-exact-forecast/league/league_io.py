import json
from pathlib import Path
import numpy as np
import pandas as pd

try:
    from league.engine import Fixture, History, PlayerTable, VenueTable
except ImportError:
    from engine.model import Fixture, History, PlayerTable, VenueTable

def _lineup_rows(key, fixtures):
    # one row per player per match: batting slot 0 to 10, and bowling slot 0 to 4 for the five who bowl, else -1
    rows = []
    for f in fixtures:
        for team, xi, five in ((f.home, f.home_xi, f.home_bowlers), (f.away, f.away_xi, f.away_bowlers)):
            slot = {int(p): i for i, p in enumerate(five)}
            rows += [(f.match, team, i, int(p), slot.get(int(p), -1)) for i, p in enumerate(xi)]
    return pd.DataFrame(rows, columns=[key, "team", "batting_slot", "player", "bowling_slot"])


def save_league(folder, history, fixtures):
    # seven CSV files and one JSON file, all public; outcomes and roles are written as words so the files read naturally
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    balls = history.balls.copy()
    balls["outcome"] = np.array(["W", "0", "1", "2", "4", "6"])[balls.outcome]
    balls.to_csv(folder / "balls.csv", index=False)
    history.matches.to_csv(folder / "matches.csv", index=False)
    _lineup_rows("match", history.played).to_csv(folder / "lineups.csv", index=False)
    p = history.players
    pd.DataFrame({"player": np.arange(len(p.role)), "role": np.array(["batter", "allrounder", "bowler"])[p.role], "hand": np.array(["right", "left"])[p.hand],
                  "bowling_style": np.array(["pace", "spin"])[p.style]}).to_csv(folder / "players.csv", index=False)
    v = history.venues
    pd.DataFrame({"venue": np.arange(len(v.pitch)), "home_team": v.home_team, "pitch": np.array(["neutral", "pace", "spin"])[v.pitch]}).to_csv(folder / "venues.csv", index=False)
    pd.DataFrame([(f.match, f.season, f.home, f.away, f.venue) for f in fixtures], columns=["fixture", "season", "home", "away", "venue"]).to_csv(folder / "fixtures.csv", index=False)
    _lineup_rows("fixture", fixtures).to_csv(folder / "fixture_lineups.csv", index=False)
    (folder / "meta.json").write_text(json.dumps({"seasons": history.seasons}))


def _fixtures(table, lineups, key):
    # rebuilds Fixture objects from the fixtures table and the line-up rows
    out = []
    for row in table.itertuples():
        ident = getattr(row, key)
        mine = lineups[lineups[key] == ident]
        side = {}
        for team in (row.home, row.away):
            t = mine[mine.team == team].sort_values("batting_slot")
            side[team] = (t.player.to_numpy(), t[t.bowling_slot >= 0].sort_values("bowling_slot").player.to_numpy())
        out.append(Fixture(int(ident), int(row.season), int(row.home), int(row.away), int(row.venue), side[row.home][0], side[row.home][1], side[row.away][0], side[row.away][1]))
    return out


def load_league(folder):
    """Returns (history, fixtures) exactly as the reference forecasters use them."""
    folder = Path(folder)
    # outcome is read as text so that "0" stays a label and does not become a number
    balls = pd.read_csv(folder / "balls.csv", dtype={"outcome": str})
    balls["outcome"] = balls.outcome.map({"W": 0, "0": 1, "1": 2, "2": 3, "4": 4, "6": 5}).astype(int)
    players, venues = pd.read_csv(folder / "players.csv"), pd.read_csv(folder / "venues.csv")
    table = PlayerTable(players.role.map({"batter": 0, "allrounder": 1, "bowler": 2}).to_numpy(), players.hand.map({"right": 0, "left": 1}).to_numpy(),
                        players.bowling_style.map({"pace": 0, "spin": 1}).to_numpy())
    grounds = VenueTable(venues.home_team.to_numpy(), venues.pitch.map({"neutral": 0, "pace": 1, "spin": 2}).to_numpy())
    seasons = json.loads((folder / "meta.json").read_text())["seasons"]
    history = History(balls, pd.read_csv(folder / "matches.csv"), table, grounds, [], seasons)