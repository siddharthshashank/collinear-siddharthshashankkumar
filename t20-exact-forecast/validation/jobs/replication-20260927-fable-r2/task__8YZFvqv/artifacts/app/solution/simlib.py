"""Vectorized match simulator matching engine.model exactly, but every hidden number may differ per copy.
Shapes: style (n,11), quality (n,11,5), conditions (n,11,5), kind (n,5), bowl_quality (n,5), shift (n,)."""
import numpy as np
from engine.model import RUNS

def play(model, style, quality, conditions, kind, bowlq, shift, n, gen, target=None):
    m = model; rows = np.arange(n)
    striker, partner, next_in = np.zeros(n, int), np.ones(n, int), np.full(n, 2)
    wickets = np.zeros(n, int); runs = np.zeros(n, int); live = np.ones(n, bool)
    chasing = 0.0 if target is None else 1.0
    chase_vec = np.full(n, chasing)
    cal = m.cal
    for ball in range(120):
        over = ball // 6; who = over % 5
        pressure = 0.0 if target is None else m.pressure(target, runs, ball)
        z = m.situation(over, striker, wickets, chase_vec, pressure)
        z = z + np.outer(style[rows, striker], m.bs) + np.outer(quality[rows, striker, who], m.bq)
        z = z + np.outer(kind[:, who], m.wt) + np.outer(bowlq[:, who], m.wq) + np.outer(shift + conditions[rows, striker, who], m.c)
        p = m.shares(z)
        kind_ = np.minimum((gen.random(n)[:, None] > p.cumsum(axis=1)).sum(axis=1), 5)
        extra = (gen.random(n) < cal.extras_per_ball) & live
        out = (kind_ == 0) & live
        scored = np.where(live & ~out, RUNS[kind_], 0)
        runs += scored + extra
        wickets += out
        striker = np.where(out, next_in, striker)
        next_in = next_in + out
        swap = (scored % 2 == 1) ^ (ball % 6 == 5)
        striker, partner = np.where(swap, partner, striker), np.where(swap, striker, partner)
        striker, partner = np.minimum(striker, 10), np.minimum(partner, 10)
        live &= wickets < 10
        if target is not None:
            live &= runs < target
    return runs

def win_probability(model, cards, n, gen, day_sd):
    """cards: dict with for each order (first, second) in ((home, away), (away, home)):
       functions giving (style, quality, conditions, kind, bowlq, shift_first, shift_second) arrays for n copies.
       Returns P(home wins)."""
    total = 0.0
    for order in (0, 1):
        day = gen.normal(0.0, day_sd, n) if day_sd > 0 else np.zeros(n)
        bat1, bowl1, sh1, bat2, bowl2, sh2 = cards(order, n)
        set_ = play(model, *bat1, *bowl1, sh1 + day, n, gen)
        chase = play(model, *bat2, *bowl2, sh2 + day, n, gen, target=set_ + 1)
        second_wins = (chase > set_).mean() + 0.5 * (chase == set_).mean()
        total += 0.5 * (second_wins if order == 1 else 1 - second_wins)   # order 0: home bats first
    return float(total)
