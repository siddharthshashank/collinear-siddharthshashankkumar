import numpy as np
import pandas as pd

balls = pd.read_pickle("data/balls.pkl")
# recent seasons only, because the game has changed a lot since 2008; super overs are already gone
balls = balls[(balls.season >= 2019) & (balls.innings <= 2)].copy()
# a legal ball is one that counts toward the six in an over
balls["legal"] = ~balls.wide & ~balls.noball
# how many legal balls had been bowled in this innings before this one
balls["balls_before"] = balls.groupby(["match", "innings"], sort=False).legal.cumsum() - balls.legal
# keep legal balls inside the 120 of a full innings
legal = balls[balls.legal & (balls.balls_before < 120)].copy()
# over 1 is balls 0 to 5, over 2 is balls 6 to 11, and so on
legal["over"] = (legal.balls_before // 6).astype(int) + 1
# the six outcomes: a wicket to the bowler, or the batter's runs with 3 counted as 2 and 5 as 4
legal["kind"] = np.select([legal.bowler_wicket, legal.runs_bat == 0, legal.runs_bat == 1,
                           legal.runs_bat.isin([2, 3]), legal.runs_bat.isin([4, 5])], ["W", "0", "1", "2", "4"], "6")
# share of each outcome within each over
shares = pd.crosstab(legal.over, legal.kind, normalize="index")[["W", "0", "1", "2", "4", "6"]]
print(len(legal), "legal balls")
print(shares.loc[[1, 4, 10, 16, 20]].round(3).to_string())