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

# The model: one score per outcome, built by adding effects
seasons = sorted(L.season.unique())
columns = [f"over{o}" for o in range(20)] + [f"season{s}" for s in seasons[1:]] + ["inn2", "wk_excess", "pressure", "pos45", "pos67", "pos8plus"]
# X has one row per ball and one column per effect
X = np.zeros((len(L), len(columns)))
# which over the ball was in: a 1 in exactly one of the first twenty columns
X[np.arange(len(L)), L.over.to_numpy()] = 1
# which season, with the first season as the baseline
for j, s in enumerate(seasons[1:]):
    X[:, 20 + j] = (L.season == s)
base = 20 + len(seasons) - 1
X[:, base] = (L.innings == 2)
X[:, base + 1] = L.wk_excess
X[:, base + 2] = L.pressure
X[:, base + 3] = L.pos.between(4, 5)
X[:, base + 4] = L.pos.between(6, 7)
X[:, base + 5] = L.pos >= 8
y = L.kind.to_numpy()
# Y has a 1 in the column of the outcome that happened
Y = np.eye(6)[y]
# the outcome "1 run" (index 2) is the reference, its scores are fixed at zero
FREE = [0, 1, 3, 4, 5]

def objective(theta):
    # B would hold one score per effect per outcome
    B = np.zeros((X.shape[1], 6))
    B[:, FREE] = theta.reshape(X.shape[1], 5)
    # each ball's six scores are the sum of the effects that apply to it
    z = X @ B
    # subtracting the row maximum changes nothing mathematically and stops exp() overflowing
    z -= z.max(1, keepdims = True)
    p = np.exp(z)
    p /= p.sum(1, keepdims = True)
    # Find whether the model is surprised by what happened, plus a light penalty on large numbers
    loss = -np.log(p[np.arange(len(y)), y]).sum() + 0.5 * 1e-2 * (theta ** 2).sum()
    # Slope of the loss w.r.t. every number in B
    gradient = (X.T @ (p - Y))[:, FREE].ravel() + 1e-2 * theta
    return loss, gradient

fit = minimize(objective, np.zeros(X.shape[1] * 5), jac=True, method="L-BFGS-B", options={"maxiter": 400})
B = np.zeros((X.shape[1], 6))
B[:, FREE] = fit.x.reshape(X.shape[1], 5)
names = ["W", "0", "1", "2", "4", "6"]
show = lambda v: "  ".join(f"{n}:{x:+.3f}" for n, x in zip(names, v - v.mean()))
print(X.shape[1], "columns,", X.shape[1] * 5, "free numbers | converged:", fit.success, "| iterations:", fit.nit)
print("one more wicket lost than usual  ", show(B[base + 1]))
print("one unit of chase pressure       ", show(B[base + 2]))
print("second innings, on average       ", show(B[base]))
print("batting at 8 or lower            ", show(B[base + 5]))

# Directions in which players differ
# the model's probabilities for every ball, given only the situation
z = X @ B
z -= z.max(1, keepdims = True)
P = np.exp(z)
P /= P.sum(1, keepdims = True)

def directions(who, floor):
    groups = L.groupby(who)
    # observed: how many times each outcome happened to each player
    observed = np.array([np.bincount(y[rows], minlength = 6) for rows in groups.indices.values()])
    # expected: how often it would have happened to an average player in exactly the same situations
    expected = np.vstack([P[rows].sum(0) for rows in groups.indices.values()])
    keep = observed.sum(1) >= floor
    observed, expected = observed[keep], expected[keep]
    # each player's tilt: log of observed over expected, centred so the six numbers sum to zero
    tilt = np.log((observed + 0.5) / (expected + 0.5))
    tilt -= tilt.mean(1, keepdims = True)
    weights = observed.sum(1) / observed.sum()
    # how the tilts vary together across players, minus what sampling noise alone would produce
    noise = np.diag((weights[:, None] / (expected + 0.5)).sum(0))
    covariance = (tilt * weights[:, None]).T @ tilt - noise
    values, vectors = np.linalg.eigh((covariance + covariance.T) / 2)
    order = np.argsort(values)[::-1]
    values, vectors = values[order], vectors[:, order]
    # fix the sign so that the first direction points toward more sixes
    first = vectors[:, 0] * np.sign(vectors[5, 0])
    return int(keep.sum()), values, first, vectors[:, 1]


centre = lambda rows: rows - rows.mean(1, keepdims=True)
out = {"overs": centre(B[:20]).round(4).tolist(),
       "season_effects": {str(s): (B[20 + j] - B[20 + j].mean()).round(4).tolist() for j, s in enumerate(seasons[1:])},
       "wk_excess": (B[base + 1] - B[base + 1].mean()).round(4).tolist(), "pressure": (B[base + 2] - B[base + 2].mean()).round(4).tolist(),
       "inn2": (B[base] - B[base].mean()).round(4).tolist(), "pos": centre(B[base + 3:base + 6]).round(4).tolist(),
       "typical_wk": typical_wk.round(3).tolist(), "par_from": par_from.round(3).tolist()}
for who, floor in (("batter", 300), ("bowler", 300)):
    n, values, first, second = directions(who, floor)
    share = np.clip(values, 0, None) / np.clip(values, 0, None).sum()
    print(f"{who}s with {floor}+ balls: {n} | share of real variation on the first three directions: {np.round(share[:3], 2)} | spread along the first: {np.sqrt(max(values[0], 0)):.3f}")
    print("   first direction  ", show(first))
    print("   second direction ", show(second * np.sign(second[0])))
    out[who] = {"direction": first.round(4).tolist(), "sd": round(float(np.sqrt(max(values[0], 0))), 4), "second": second.round(4).tolist(), "shares": share[:3].round(3).tolist()}
json.dump(out, open("data/state_fit.json", "w"), indent=1)
print("saved data/state_fit.json")