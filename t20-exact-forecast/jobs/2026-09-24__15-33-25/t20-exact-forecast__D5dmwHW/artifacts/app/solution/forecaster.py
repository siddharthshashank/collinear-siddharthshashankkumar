"""Build a skill book from the MAP fit and simulate fixtures."""
import numpy as np
from engine.model import SkillBook, MatchSimulator


def book_from_theta(design, hist, theta, hyper, era_mode="last"):
    d = design
    T, S = d.T, d.ns
    blk = lambda k: d.block(theta, k)
    qual = blk("qual").reshape(-1, T)[:, T - 1]
    bowlq = blk("bowlq").reshape(-1, T)[:, T - 1]
    kind = blk("kindmean")[hist.players.style] + blk("kind")
    era = blk("era")
    era_now = era[S - 1] if era_mode == "last" else era[S]
    return SkillBook(hist.players, hist.venues, blk("style"), qual, blk("split"), kind, bowlq,
                     blk("type").reshape(2, 2), blk("pitch").reshape(2, 3), blk("venue"), blk("dew"), blk("aff").reshape(-1, d.nv),
                     float(blk("home")[0]), float(era_now), float(hyper["sd_day"]), float(blk("wear")[0]))


def forecast(design, hist, fixtures, theta, hyper, model, n=4000, draws=None, cov_chol=None, seed=0):
    """P(home wins) for each fixture. If draws > 0 and cov_chol given, average over posterior samples of theta."""
    ms = MatchSimulator(model)
    gen = np.random.default_rng(seed)
    out = []
    if not draws:
        book = book_from_theta(design, hist, theta, hyper)
        return np.array([ms.win_probability(book, f, n, gen) for f in fixtures])
    samples = theta[None, :] + (cov_chol @ gen.standard_normal((len(theta), draws))).T
    per = max(n // draws, 50)
    ps = np.zeros(len(fixtures))
    for s in range(draws):
        book = book_from_theta(design, hist, samples[s], hyper)
        ps += np.array([ms.win_probability(book, f, per, gen) for f in fixtures])
    return ps / draws


def regret(p, q):
    q = np.clip(q, 0.002, 0.998)
    p = np.asarray(p)
    with np.errstate(divide="ignore", invalid="ignore"):
        a = np.where(p > 0, p * np.log(p / q), 0.0)
        b = np.where(p < 1, (1 - p) * np.log((1 - p) / (1 - q)), 0.0)
    return a + b
