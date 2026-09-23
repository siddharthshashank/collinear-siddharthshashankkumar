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

def residuals():
    # The starting point for the venue and interaction tests: every ball's runs off the bat relative to
    # that season's average. Subtracting the season mean removes the rise in scoring over the years, so a
    # ground that hosted more recent matches does not look high-scoring just because scoring rose.
    # Every match is also assigned to one of two halves (odd or even in the archive's order), so that any
    # effect can be tested for whether it repeats across independent sets of matches.
    faced = balls[~balls.wide].copy()
    faced["res"] = faced.runs_bat - faced.groupby("season").runs_bat.transform("mean")
    faced["half"] = pd.factorize(faced.match)[0] % 2
    return faced

def venue_spread():
    # Do grounds really differ, and by how much? For each ground with at least 2,000 balls in each half,
    # compute the mean residual in each half and correlate across grounds. A high correlation means a ground
    # that scores high in one set of matches also scores high in the other, so the difference is real.
    # The true spread is the observed spread of ground means scaled by the square root of the Spearman-Brown
    # reliability, the same correction as for batters. Expect 18 grounds, repeat 0.71, true spread 0.045
    # runs per ball, which is about five runs an innings between a typical ground and a high-scoring one.
    faced = residuals()
    v = faced.groupby(["venue", "half"]).res.agg(mean = "mean", n = "size").unstack()
    v = v[(v[("n", 0)] >= 2000) & (v[("n", 1)] >= 2000)]
    r = v[("mean", 0)].corr(v[("mean", 1)])
    both = faced[faced.venue.isin(v.index)].groupby("venue").res.mean()
    return {"venues": int(len(v)), "repeat": round(float(r), 2), "true_sd_runs_per_ball": round(float(both.std() * np.sqrt(2 * r / (1 + r))), 4)}

def interaction(first, second, floor):
    # Does a specific pair (batter and bowler, batter and ground, bowler and ground) have an effect beyond
    # what each side brings on its own? First remove each side's own level, computed within the same season
    # and the same half, so only what is special to the pair is left. Then, for pairs with at least `floor`
    # balls in each half, ask whether the leftover in one half predicts the leftover in the other.
    # A real effect repeats; luck does not. The levels are removed within each half deliberately: if they
    # were computed from all the data, each half's leftover would carry a negative echo of the other half
    # and the correlation would be biased downward.
    # The last line turns the repeat correlation into a true spread. If r is the correlation between halves,
    # r / (1 - r) is the ratio of real variance to noise variance in one half, and the noise variance of a
    # mean over n balls is the per-ball variance over n. Expect: batter vs bowler repeats at only 0.18 on the
    # 113 best-sampled pairs, batter at venue 0.19, bowler at venue not at all.
    faced = residuals()
    for key in (first, second):
        faced["res"] = faced["res"] - faced.groupby([key, "season", "half"]).res.transform("mean")
    g = faced.groupby([first, second, "half"]).res.agg(mean = "mean", n = "size").unstack()
    g = g[(g[("n", 0)] >= floor) & (g[("n", 1)] >= floor)]
    r = float(g[("mean", 0)].corr(g[("mean", 1)]))
    n_mean = float(np.sqrt(g[("n", 0)] * g[("n", 1)]).mean())
    true_var = max(r, 0.0) / max(1 - r, 1e-9) * float(faced.res.var()) / n_mean
    return {"pairs": int(len(g)), "repeat": round(r, 3), "balls_per_half": round(n_mean, 1), "true_sd_runs_per_ball": round(float(np.sqrt(true_var)), 4)}

def targets():
    # The real-cricket numbers a simulated league has to reproduce before anyone trusts it. From the four
    # most recent seasons: the mean and spread of first-innings totals, wickets taken by bowlers in a first
    # innings, how often the chasing side wins, and the run rate in each over of a first innings. From 2019
    # onward (more matches, so the bands are better filled): how often a chase succeeds by size of target.
    # None of these enters the simulator directly. They are the checks in validate_world.py.
    inn = recent.groupby(["match", "innings"]).agg(total = ("runs_total", "sum"), wickets = ("bowler_wicket", "sum")).reset_index()
    first = inn[inn.innings == 1]
    second = inn[inn.innings == 2].set_index("match").total
    chase = float((second.reindex(first.match).to_numpy() > first.total.to_numpy()).mean())
    legal = recent[~recent.wide & ~recent.noball & (recent.innings == 1)].copy()
    legal["over"] = legal.over_ball.astype(int)
    per_over = (legal.groupby("over").runs_total.sum() / legal.groupby("over").size() * 6).round(2).tolist()
    totals = balls[balls.season >= 2019].groupby(["match", "innings"]).runs_total.sum().unstack().dropna()
    bands = {}
    for lo, hi in ((0, 160), (160, 180), (180, 200), (200, 220), (220, 400)):
        m = totals[(totals[1] + 1 >= lo) & (totals[1] + 1 < hi)]
        bands[f"{lo}-{hi}"] = [int(len(m)), round(float((m[2] > m[1]).mean()), 3)]
    return {"first_innings_mean": round(float(first.total.mean()), 1), "first_innings_sd": round(float(first.total.std()), 1),
            "first_innings_wickets": round(float(first.wickets.mean()), 2), "chasing_side_wins": round(chase, 3),
            "runs_per_over_first_innings": per_over, "chase_success_by_target": bands}