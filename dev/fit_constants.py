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