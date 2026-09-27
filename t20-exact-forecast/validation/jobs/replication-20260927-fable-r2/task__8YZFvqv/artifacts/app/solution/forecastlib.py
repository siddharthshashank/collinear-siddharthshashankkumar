"""From a fitted Design to fixture win probabilities."""
import numpy as np
from engine.model import PACE, SPIN
import simlib

def card_builder(des, theta, Sig, fixture, weights, n_samples, gen, sample=True):
    """Returns cards(order, n) for simlib.win_probability. Skills drawn from the Laplace posterior (or plugged in)."""
    B, pl, ve = des.B, des.hist.players, des.hist.venues
    f = fixture; T = des.T; nP, nV = des.nP, des.nV
    xi_all = np.concatenate([f.home_xi, f.away_xi]); bw_all = np.concatenate([f.home_bowlers, f.away_bowlers])
    # parameter indices needed
    need = {}
    def reg(name, idx): need[name] = np.asarray(idx)
    reg('style', B['style'][xi_all]); reg('style_mean', B['style_mean']); reg('bat_mean', B['bat_mean'])
    reg('bat_q', B['bat_q'].reshape(nP, T)[xi_all].ravel()); reg('split', B['split'][xi_all])
    reg('kind', B['kind'][bw_all]); reg('kind_mean', B['kind_mean']); reg('bowl_mean', B['bowl_mean'])
    reg('bowl_q', B['bowl_q'].reshape(nP, T)[bw_all].ravel())
    reg('venue', B['venue'][[f.venue]]); reg('era', B['era'][[des.nS - 1]]); reg('chase', B['chase'][[f.venue]]); reg('chase_mean', B['chase_mean'])
    reg('affinity', B['affinity'].reshape(nP, nV)[xi_all, f.venue]); reg('home', B['home']); reg('type', B['type']); reg('pitch', B['pitch'])
    allidx = np.concatenate(list(need.values()))
    offs = {}; o = 0
    for k, v in need.items(): offs[k] = slice(o, o + len(v)); o += len(v)
    mu = theta[allidx]
    if sample:
        C = Sig[np.ix_(allidx, allidx)]
        # add prediction-step variance of quality for the fixture period via weights below (handled analytically)
        L = np.linalg.cholesky(C + 1e-10 * np.eye(len(allidx)))
        draws = mu[None, :] + gen.normal(size=(n_samples, len(allidx))) @ L.T
    else:
        draws = np.repeat(mu[None, :], n_samples, axis=0)
    S = n_samples
    def get(k): return draws[:, offs[k]]
    wb, ww = weights['bat'], weights['bowl']   # length-T weights predicting fixture-period quality from period qualities
    style = get('style') + get('style_mean')[:, pl.role[xi_all]]
    batq = (get('bat_q').reshape(S, len(xi_all), T) @ wb) + get('bat_mean')[:, pl.role[xi_all]]
    if sample:
        batq = batq + np.sqrt(max(weights['bat_resid'], 0)) * gen.normal(size=batq.shape)
    split = get('split')
    kind = get('kind') + get('kind_mean')[:, pl.style[bw_all]]
    bowlq = (get('bowl_q').reshape(S, len(bw_all), T) @ ww) + get('bowl_mean')[:, pl.role[bw_all]]
    if sample:
        bowlq = bowlq + np.sqrt(max(weights['bowl_resid'], 0)) * gen.normal(size=bowlq.shape)
    base = get('venue')[:, 0] + get('era')[:, 0]
    chase = get('chase')[:, 0] + get('chase_mean')[:, 0]
    aff = get('affinity'); home = get('home')[:, 0]; typ = get('type'); pit = get('pitch')
    hand = pl.hand[xi_all]; pitch = ve.pitch[f.venue]
    side = np.r_[np.zeros(11, int), np.ones(11, int)]   # 0 home batters, 1 away batters
    def cards(order, n):
        rep = np.arange(n) % S
        # order 0: home bats first (vs away bowlers), away chases (vs home bowlers); order 1 reverse
        first_side = 0 if order == 0 else 1
        out = []
        for inn, bside in enumerate((first_side, 1 - first_side)):
            bidx = np.where(side == bside)[0]; wside = 1 - bside
            widx = np.arange(5) + 5 * wside
            how = pl.style[bw_all[widx]]                        # (5,)
            sign = np.where(how == PACE, 0.5, -0.5)
            q = batq[:, bidx][:, :, None] + split[:, bidx][:, :, None] * sign[None, None, :]   # (S,11,5)
            at_home = home if (ve.home_team[f.venue] == (f.home if bside == 0 else f.away)) else np.zeros(S)
            meet = (aff[:, bidx] + at_home[:, None])[:, :, None] + typ[:, (hand[bidx][:, None] * 2 + how[None, :])] + pit[:, (how * 3 + pitch)][:, None, :]
            bat = (style[:, bidx][rep], q[rep], meet[rep])
            bowl = (kind[:, widx][rep], bowlq[:, widx][rep])
            sh = base + (chase if inn == 1 else 0.0)
            out += [bat, bowl, sh[rep]]
        return tuple(out)
    return cards

def prediction_weights(K_full, T):
    """K_full: (T+1)x(T+1) prior covariance over periods + fixture period. Returns weights and residual variance."""
    Kpp = K_full[:T, :T]; kfp = K_full[T, :T]
    w = np.linalg.solve(Kpp, kfp)
    resid = K_full[T, T] - kfp @ w
    return w, float(resid)
