import json
import numpy as np
import pandas as pd

balls = pd.read_pickle("data/balls.pkl")
balls = balls[balls.innings <= 2].copy()
# a ground's name is the text before the first comma, so the same ground is not counted twice under two spellings
balls["venue"] = balls.venue.str.split(",").str[0].str.strip()
recent = balls[balls.season >= 2023]

def extras_per_legal_ball():
    # how many extra runs (wides, no balls, byes, leg byes) the fielding side gives away per legal ball.
    # Simulator adds this on top of the six bat outcomes so that team totals come out right.
    # Team runs minus batter runs are the extras. Expect about 0.076, roughly nine runs an innings.
    legal = (~recent.wide & ~recent.noball).sum()
    return float((recent.runs_total - recent.runs_bat).sum() / legal)

def season_reliability(who, floor):
    # The split-half test from explore_reliability.py, generalized so it runs for batters or bowlers.
    # Splits each player's season into odd and even matches, correlates the scoring rate in the two halves,
    # and converts to a full-season reliability with Spearman-Brown. For a bowler the "rate" is runs
    # conceded off the bat per ball. Expect 0.46 for batters and 0.27 for bowlers: a bowler's economy
    # in one season is even noisier than a batter's strike rate.
    faced = recent[~recent.wide].copy()
    faced["half"] = faced.groupby([who, "season"]).match.transform(lambda s: pd.factorize(s)[0] % 2)
    halves = faced.groupby([who, "season", "half"]).runs_bat.agg(rate = "mean", n = "size").unstack()
    halves = halves[(halves[("n", 0)] >= floor / 2) & (halves[("n", 1)] >= floor / 2)]
    r = halves[("rate", 0)].corr(halves[("rate", 1)])
    return round(float(2 * r / (1 + r)), 2)