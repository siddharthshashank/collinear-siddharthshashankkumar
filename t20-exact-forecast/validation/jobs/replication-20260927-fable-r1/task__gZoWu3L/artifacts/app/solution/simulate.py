"""Match simulation with per-copy hidden values, so that posterior draws of the skills can be integrated over.
Mirrors engine.model.InningsSimulator / MatchSimulator exactly, but every card may carry a leading copy axis."""
import numpy as np

RUNS = np.array([0, 0, 1, 2, 4, 6])


def play_innings(model, style, quality, conditions, kind, bowl_quality, shift, n, gen, target=None):
    """style (n,11), quality (n,11,5), conditions (n,11,5), kind (n,5), bowl_quality (n,5), shift (n,) innings-wide conditions."""
    m, rows = model, np.arange(n)
    striker, partner, next_in = np.zeros(n, int), np.ones(n, int), np.full(n, 2)
    wickets = np.zeros(n, int); runs = np.zeros(n, int); live = np.ones(n, bool)
    chasing = 0.0 if target is None else 1.0
    chase_vec = np.full(n, chasing)
    for ball in range(120):
        over = ball // 6
        who = over % 5
        pressure = 0.0 if target is None else m.pressure(target, runs, ball)
        z = m.situation(over, striker, wickets, chase_vec, pressure)
        z = z + np.outer(style[rows, striker], m.bs) + np.outer(quality[rows, striker, who], m.bq)
        z = z + np.outer(kind[:, who], m.wt) + np.outer(bowl_quality[:, who], m.wq) + np.outer(shift + conditions[rows, striker, who], m.c)
        p = m.shares(z)
        kind_out = np.minimum((gen.random(n)[:, None] > p.cumsum(axis=1)).sum(axis=1), 5)
        extra = (gen.random(n) < m.cal.extras_per_ball) & live
        out = (kind_out == 0) & live
        scored = np.where(live & ~out, RUNS[kind_out], 0)
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


def expand(cards, idx):
    return {k: v[idx] for k, v in cards.items()}


def win_probability(model, sides, shift_first, shift_chase, fixture, sd_day, n_per_sample, gen):
    """sides: team -> dict of arrays with leading sample axis S. Each sample is replicated n_per_sample times. Returns P(home wins)."""
    f = fixture
    S = shift_first.shape[0]
    n = S * n_per_sample
    idx = np.repeat(np.arange(S), n_per_sample)
    home, away = expand(sides[f.home], idx), expand(sides[f.away], idx)
    sf, sc = shift_first[idx], shift_chase[idx]
    total = 0.0
    for first, second in ((home, away), (away, home)):
        day = gen.normal(0.0, sd_day, n) if sd_day > 0 else np.zeros(n)
        set_ = play_innings(model, first["style"], first["quality"], first["conditions"], second["kind"], second["bowl_quality"], sf + day, n, gen)
        chase = play_innings(model, second["style"], second["quality"], second["conditions"], first["kind"], first["bowl_quality"], sc + day, n, gen, target=set_ + 1)
        second_wins = (chase > set_).mean() + 0.5 * (chase == set_).mean()
        total += 0.5 * (second_wins if second is home else 1 - second_wins)
    return float(total)
