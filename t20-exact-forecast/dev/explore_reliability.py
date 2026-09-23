import numpy as np
import pandas as pd

balls = pd.read_pickle("data/balls.pkl")
# recent seasons, and only balls the batter actually faced (a wide is not a ball faced)
faced = balls[(balls.season >= 2023) & ~balls.wide].copy()
# number each batter's matches within a season 0, 1, 2, ... and take odd and even
faced["half"] = faced.groupby(["batter", "season"]).match.transform(lambda s: pd.factorize(s)[0] % 2)
# runs per ball and balls faced, for each batter-season, in each half
halves = faced.groupby(["batter", "season", "half"]).runs_bat.agg(rate = "mean", n = "size").unstack()
# keep batter-seasons with enough balls in both halves to mean something
halves = halves[(halves[("n", 0)] >= 60) & (halves[("n", 1)] >= 60)]
# how well does one half predict the other?
r = halves[("rate", 0)].corr(halves[("rate", 1)])
# Spearman-Brown: a full season is twice as long as half, so it is more reliable than r
reliability = 2 * r / (1 + r)
# Spread we observe across batter-seasons
whole = faced.groupby(["batter", "season"]).runs_bat.agg(rate = "mean", n = "size")
whole = whole[whole.n >= 120]
print(len(halves), "batter-seasons with 60+ balls in each half")
print("odd-even correlation r =", round(r, 3))
print("reliability of a full season =", round(reliability, 3))
print("observed spread of strike rate =", round(whole.rate.std(), 4), "runs per ball over", len(whole), "batter-seasons")
print("true spread =", round(whole.rate.std() * np.sqrt(reliability), 4), "runs per ball")