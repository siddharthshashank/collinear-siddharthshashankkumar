import argparse, os, sys, time
from pathlib import Path

# pin BLAS threads before numpy loads so the arithmetic (and hence the output) does not depend on the machine
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "2")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from engine.league_io import load_league  # noqa: E402
from engine.model import load_public_model, PACE  # noqa: E402
from fitlib import Design  # noqa: E402
from sim import DrawSimulator  # noqa: E402

# quality hyperparameters: (talent sd, form sd, weekly rho, off-season rho)
DEFAULT_HP = {"style": 0.38, "split": 0.14, "kind": 0.15, "venue": 0.05, "dew": 0.05, "affinity": 0.09, "day": 0.29,
              "quality": (0.12, 0.16, 0.96, 0.75), "bowl_quality": (0.05, 0.19, 0.96, 0.85)}
ERA_DRIFT = 0.08


def fit_league(hist, em_iters=6, hp0=None, nb=1, verbose=False):
    D = Design(hist, hist.seasons, nb=nb)
    hp = dict(hp0 or DEFAULT_HP)
    for name in D.seasonal:
        hp[name] = tuple(hp[name])
    theta, f, H = D.fit(hp)
    C = D.posterior_cov(H)
    for it in range(em_iters):
        hp = D.em_update(theta, C, hp)
        theta, f, H = D.fit(hp, theta0=theta)
        C = D.posterior_cov(H)
        if verbose:
            print(it, {k: (round(v, 4) if np.isscalar(v) else tuple(round(x, 3) for x in v)) for k, v in hp.items()}, round(f, 2), flush=True)
    return D, theta, C, hp


def forecast(folder, n=8000, seed=12345, em_iters=6, plugin=False, verbose=False, hp0=None, nb=1):
    t0 = time.time()
    hist, fixtures = load_league(folder)
    D, theta, C, hp = fit_league(hist, em_iters=em_iters, hp0=hp0, nb=nb, verbose=verbose)
    if verbose:
        print("fit done", round(time.time() - t0, 1), flush=True)
    B = D.B; P, V = hist.players, hist.venues; k = D.n_seasons
    model = load_public_model()
    sim = DrawSimulator(model)
    gen = np.random.default_rng(seed)
    fixed_idx = np.concatenate([np.arange(B.offsets[nm], B.offsets[nm] + B.size(nm)) for nm in D.fixed])
    out = []
    for fx in fixtures:
        t_fix, s_fix = fx.season * D.W + 0.5 * D.W / D.nb, fx.season
        sides = {}
        idx_list = [fixed_idx, np.array([B.idx("venue", fx.venue), B.idx("dew", fx.venue)])]
        qw, bw = {}, {}
        for team, xi, five in ((fx.home, fx.home_xi, fx.home_bowlers), (fx.away, fx.away_xi, fx.away_bowlers)):
            idx_list.append(B.idx("style", xi)); idx_list.append(B.idx("split", xi))
            for p in xi:
                sl = D.qblk.slice(p)
                idx_list.append(B.offsets["quality"] + np.arange(sl.start, sl.stop))
                qw[p] = D.forecast_weights("quality", hp, p, t_fix, s_fix)
            for p in five:
                w = D.bowler_index[p]
                if w >= 0:
                    idx_list.append(B.idx("kind", [w]))
                sl = D.wblk.slice(p)
                idx_list.append(B.offsets["bowl_quality"] + np.arange(sl.start, sl.stop))
                bw[p] = D.forecast_weights("bowl_quality", hp, p, t_fix, s_fix)
            keys = xi * D.n_venues + fx.venue
            pos = np.minimum(np.searchsorted(D.pairs, keys), len(D.pairs) - 1)
            hit = D.pairs[pos] == keys
            if hit.any():
                idx_list.append(B.idx("affinity", pos[hit]))
        idx = np.unique(np.concatenate(idx_list))
        mean = theta[idx]
        if plugin:
            draws = np.tile(mean, (n, 1))
        else:
            Cs = C[np.ix_(idx, idx)]; Cs = 0.5 * (Cs + Cs.T)
            L = np.linalg.cholesky(Cs + 1e-10 * np.eye(len(idx)))
            draws = mean[None, :] + gen.normal(size=(n, len(idx))) @ L.T
        loc = np.full(B.total, -1); loc[idx] = np.arange(len(idx))

        def col(name, *multi):
            ii = np.atleast_1d(B.idx(name, *multi))
            return draws[:, loc[ii]]

        def noise(sd, *shape):
            return 0.0 if plugin else sd * gen.normal(size=shape)

        era = col("era", k - 1)[:, 0] + noise(ERA_DRIFT, n)
        home_lift = col("home_lift", 0)[:, 0]; wear = col("wear", 0)[:, 0]
        venue = col("venue", fx.venue)[:, 0]; dew = col("dew", fx.venue)[:, 0]
        type_table = col("type_table", np.repeat([0, 1], 2), np.tile([0, 1], 2)).reshape(n, 2, 2)
        pitch_table = col("pitch_table", np.repeat([0, 1], 3), np.tile([0, 1, 2], 2)).reshape(n, 2, 3)
        style_role = col("style_role", np.arange(3)); q_role = col("q_role", np.arange(3)); kind_style = col("kind_style", np.arange(2))
        wq_cell = col("wq_cell", np.repeat([0, 1], 2), np.tile([0, 1], 2)).reshape(n, 2, 2)
        pitch = V.pitch[fx.venue]
        for team, xi, five in ((fx.home, fx.home_xi, fx.home_bowlers), (fx.away, fx.away_xi, fx.away_bowlers)):
            role = P.role[xi]; hand = P.hand[xi]
            style = style_role[:, role] + col("style", xi)
            quality = q_role[:, role].copy()
            for j, p in enumerate(xi):
                w, sd = qw[p]
                if w is not None:
                    sl = D.qblk.slice(p)
                    quality[:, j] += draws[:, loc[B.offsets["quality"] + np.arange(sl.start, sl.stop)]] @ w
                quality[:, j] += noise(sd, n)
            split = col("split", xi)
            at_home = home_lift if V.home_team[fx.venue] == team else np.zeros(n)
            aff = np.zeros((n, len(xi)))
            keys = xi * D.n_venues + fx.venue
            pos = np.minimum(np.searchsorted(D.pairs, keys), len(D.pairs) - 1); hit = D.pairs[pos] == keys
            if hit.any():
                aff[:, hit] = col("affinity", pos[hit])
            if (~hit).any():
                aff[:, ~hit] = noise(hp["affinity"], n, int((~hit).sum()))
            wstyle = P.style[five]; wrole = np.where(P.role[five] == 1, 0, 1)
            kind = kind_style[:, wstyle].copy(); bq = wq_cell[:, wrole, wstyle].copy()
            for j, p in enumerate(five):
                w_ = D.bowler_index[p]
                if w_ >= 0:
                    kind[:, j] += col("kind", [w_])[:, 0]
                else:
                    kind[:, j] += noise(hp["kind"], n)
                w, sd = bw[p]
                if w is not None:
                    sl = D.wblk.slice(p)
                    bq[:, j] += draws[:, loc[B.offsets["bowl_quality"] + np.arange(sl.start, sl.stop)]] @ w
                bq[:, j] += noise(sd, n)
            sides[team] = dict(style=style, quality=quality, split=split, hand=hand, at_home=at_home, aff=aff, kind=kind, bquality=bq, wstyle=wstyle,
                               shift_set=venue + era, shift_chase=venue + era + dew + wear)
        cards = {}
        for team, other in ((fx.home, fx.away), (fx.away, fx.home)):
            s, o = sides[team], sides[other]
            how = o["wstyle"]; sign = np.where(how == PACE, 0.5, -0.5)
            quality = s["quality"][:, :, None] + s["split"][:, :, None] * sign[None, None, :]
            meeting = (s["aff"] + s["at_home"][:, None])[:, :, None] + type_table[:, s["hand"]][:, :, how] - pitch_table[:, how, pitch][:, None, :]
            cards[team] = dict(style=s["style"], quality=quality, cond=meeting, kind=s["kind"], bquality=s["bquality"],
                               shift_set=s["shift_set"], shift_chase=s["shift_chase"])
        day = gen.normal(0.0, hp["day"], n)
        p = sim.win_probability(cards[fx.home], cards[fx.away], day, n, gen)
        out.append((fx.match, p))
        if verbose:
            print(fx.match, round(p, 4), round(time.time() - t0, 1), flush=True)
    return pd.DataFrame(out, columns=["fixture", "p_home"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=30000); ap.add_argument("--nb", type=int, default=2); ap.add_argument("--em", type=int, default=10)
    ap.add_argument("--verbose", action="store_[REDACTED]")
    a = ap.parse_args()
    attempts = [dict(n=a.n, nb=a.nb, em_iters=a.em), dict(n=10000, nb=1, em_iters=4), dict(n=4000, nb=1, em_iters=0, plugin=True)]
    df = None
    for opts in attempts:
        try:
            df = forecast(a.league, verbose=a.verbose, **opts)
            break
        except Exception as e:  # fall back to a simpler configuration rather than fail
            print("forecast attempt failed:", repr(e), file=sys.stderr, flush=True)
    fixtures = pd.read_csv(Path(a.league) / "fixtures.csv")
    if df is None:
        df = pd.DataFrame({"fixture": fixtures.fixture, "p_home": 0.5})
    df = fixtures[["fixture"]].merge(df, on="fixture", how="left")
    df["p_home"] = df.p_home.fillna(0.5).clip(0.002, 0.998)
    df.to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
