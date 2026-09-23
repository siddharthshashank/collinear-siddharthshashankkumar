import json
import numpy as np
import pandas as pd
from scipy.optimize import minimize

balls = pd.read_pickle("data/balls.pkl")
balls = balls[(balls.season >= 2019) & (balls.innings <= 2)].copy()
balls["legal"] = ~balls.wide & ~balls.noball
innings = balls.groupby(["match", "innings"], sort = False)
# state BEFORE each ball: legal balls bowled, wickets lost, runs scored
balls["balls_before"] = innings.legal.cumsum() - balls.legal
balls["wk_before"] = innings.wicket_any.cumsum() - balls.wicket_any
balls["runs_before"] = innings.runs_total.cumsum() - balls.runs_total
# the chasing side needs one more than the first-innings total
first_total = balls[balls.innings == 1].groupby("match").runs_total.sum()
balls["target"] = balls.match.map(first_total) + 1
# batting position: the order in which players first face a ball in an innings (anyone who never faces one comes last)
faced_first = pd.concat([balls[["match", "innings", "batter"]].rename(columns={"batter": "player"}),
                         balls[["match", "innings", "non_striker"]].rename(columns={"non_striker": "player"})]).drop_duplicates()
faced_first["pos"] = faced_first.groupby(["match", "innings"]).cumcount() + 1
balls = balls.merge(faced_first.rename(columns={"player": "batter"}), on=["match", "innings", "batter"], how="left")

# L is the table the model is fitted on: legal balls inside the 120 of an innings
L = balls[balls.legal & (balls.balls_before < 120)].copy()
L["over"] = (L.balls_before // 6).astype(int)
# outcomes numbered 0 to 5: W, dot, 1, 2 (or 3), 4 (or 5), 6
L["kind"] = np.select([L.bowler_wicket, L.runs_bat == 0, L.runs_bat == 1, L.runs_bat.isin([2, 3]), L.runs_bat.isin([4, 5])], [0, 1, 2, 3, 4], 5)
first = L[L.innings == 1]
# how many wickets a side has usually lost by each over, and how far this side is from that
typical_wk = first.groupby("over").wk_before.mean()
L["wk_excess"] = L.wk_before - L.over.map(typical_wk)
# the usual run rate from each over to the end of the innings
per_over = first.groupby("over").runs_total.sum() / first.groupby("over").size() * 6
par_from = per_over[::-1].expanding().mean()[::-1]
# chase pressure: log of the rate the chasing side needs over the rate sides usually manage from here
overs_left = (120 - L.balls_before) / 6
need = (L.target - L.runs_before).clip(lower=1) / overs_left
L["pressure"] = np.where(L.innings == 2, np.clip(np.log(need / L.over.map(par_from)), -1.0, 1.2), 0.0)

print(len(L), "legal balls")
print("usual wickets lost by over 10 and over 20:", round(typical_wk[9], 2), round(typical_wk[19], 2))
print("usual run rate from over 1 to the end, and in over 20 alone:", round(par_from[0], 2), round(par_from[19], 2))
print("mean chase pressure in second innings:", round(L[L.innings == 2].pressure.mean(), 3))
print("share of balls faced by positions 8 and lower:", round((L.pos >= 8).mean(), 3))