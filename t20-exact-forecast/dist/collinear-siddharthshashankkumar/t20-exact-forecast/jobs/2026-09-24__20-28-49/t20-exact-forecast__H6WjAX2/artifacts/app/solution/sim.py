"""Innings/match simulator where every hidden quantity may differ per copy (posterior draws)."""
import numpy as np
from engine.model import RUNS


class DrawSimulator:
    def __init__(self, model):
        self.m = model

    def play(self, style, quality, kind, bquality, cond, shift, n, gen, target=None):
        """style (n,11); quality (n,11,5); kind (n,5); bquality (n,5); cond (n,11,5); shift (n,) -> totals (n,)"""
        m, rows = self.m, np.arange(n)
        striker, partner, next_in = np.zeros(n, int), np.ones(n, int), np.full(n, 2)
        wickets = np.zeros(n, int); runs = np.zeros(n, int); live = np.ones(n, bool)
        chasing = 0.0 if target is None else 1.0
        chase_vec = np.full(n, chasing)
        for ball in range(120):
            over = ball // 6; who = over % 5
            pressure = 0.0 if target is None else m.pressure(target, runs, ball)
            z = m.situation(over, striker, wickets, chase_vec, pressure)
            z = z + np.outer(style[rows, striker], m.bs) + np.outer(quality[rows, striker, who], m.bq)
            z = z + np.outer(kind[:, who], m.wt) + np.outer(bquality[:, who], m.wq) + np.outer(shift + cond[rows, striker, who], m.c)
            p = m.shares(z)
            kind_ = np.minimum((gen.random(n)[:, None] > p.cumsum(axis=1)).sum(axis=1), 5)
            extra = (gen.random(n) < m.cal.extras_per_ball) & live
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

    def win_probability(self, home, away, day, n, gen):
        """home/away: dict with per-copy arrays: style, quality (vs the other side's five), kind, bquality, cond, shift_set, shift_chase.
        day: (n,) shared pitch effect. Returns P(home wins)."""
        total = 0.0
        for first, second in ((home, away), (away, home)):
            set_ = self.play(first['style'], first['quality'], second['kind'], second['bquality'], first['cond'], first['shift_set'] + day, n, gen)
            chase = self.play(second['style'], second['quality'], first['kind'], first['bquality'], second['cond'], second['shift_chase'] + day, n, gen, target=set_ + 1)
            second_wins = (chase > set_).mean() + 0.5 * (chase == set_).mean()
            total += 0.5 * (second_wins if second is home else 1 - second_wins)
        return float(total)
