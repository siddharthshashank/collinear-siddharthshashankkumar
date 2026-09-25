"""Empirical-Bayes ball model and deterministic Monte Carlo match forecasts."""
import os
# Keep the linear algebra within the two-core evaluation budget.
for _key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '2'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import time
import numpy as np
import pandas as pd
from scipy import sparse, linalg, optimize
from engine.league_io import load_league
from engine.model import load_public_model, SkillBook


class Estimator:
    def __init__(self, history, verbose=False):
        self.h = history
        self.m = load_public_model()
        self.verbose = verbose
        b = history.balls
        self.P = len(history.players.role)
        self.V = len(history.venues.pitch)
        self.S = int(b.season.max()) + 1
        self.N = len(b)
        self.bowlers = np.unique(b.bowler)
        self.B = len(self.bowlers)
        bm = np.zeros(self.P, dtype=int)
        bm[self.bowlers] = np.arange(self.B)
        self.bm = bm
        self.groups = {}
        self.terms = [[] for _ in range(5)]
        self.npar = 0
        bat, bow = b.batter.to_numpy(), b.bowler.to_numpy()
        season, venue = b.season.to_numpy(), b.venue.to_numpy()
        role = history.players.role
        how = history.players.style[bow]
        sign = np.where(how == 0, .5, -.5)
        chase = (b.innings.to_numpy() == 2).astype(float)
        home = (history.venues.home_team[venue] == b.batting_team.to_numpy()).astype(float)
        # Gaussian random effects; quality uses a talent-plus-form covariance.
        self.add('style', self.P, 0, bat, variance=.14)
        self.add('bat_mean', 3, 0, role[bat], variance=.01, fixed=True)
        self.add('bat_global', 1, 0, np.zeros(self.N,int), variance=1., fixed=True)
        self.add('quality', self.P*self.S, 1, bat*self.S+season, temporal=True, variance=(.03,.02))
        self.add('quality_mean', 3, 1, role[bat], variance=.01, fixed=True)
        self.add('quality_global', 1, 1, np.zeros(self.N,int), variance=1., fixed=True)
        self.add('split', self.P, 1, bat, sign, variance=.02)
        self.add('kind', self.B, 2, bm[bow], variance=.03)
        self.add('kind_mean', 2, 2, how, variance=1., fixed=True)
        self.add('bowl_quality', self.B*self.S, 3, bm[bow]*self.S+season, temporal=True, variance=(.02,.02))
        self.add('bowl_mean', 3, 3, role[bow], variance=.01, fixed=True)
        self.add('bowl_global', 1, 3, np.zeros(self.N,int), variance=1., fixed=True)
        self.add('venue', self.V, 4, venue, variance=.01)
        self.add('dew', self.V, 4, venue, chase, variance=.006)
        self.add('chase_mean', 1, 4, np.zeros(self.N,int), chase, variance=.25, fixed=True)
        self.add('era', self.S, 4, season, variance=1., fixed=True)
        self.add('home', 1, 4, np.zeros(self.N,int), home, variance=.25, fixed=True)
        self.add('affinity', self.P*self.V, 4, bat*self.V+venue, variance=.015)
        mids, mi = np.unique(b.match.to_numpy(), return_inverse=True)
        self.add('day', len(mids), 4, mi, variance=.08)
        self.add('type', 4, 4, history.players.hand[bat]*2+how, variance=.0225, fixed=True)
        self.add('pitch', 6, 4, how*3+history.venues.pitch[venue], -np.ones(self.N), variance=.0225, fixed=True)
        self.A = []
        for terms in self.terms:
            rr, cc, vv = [], [], []
            for ix, val in terms:
                rr.append(np.arange(self.N)); cc.append(ix); vv.append(val)
            self.A.append(sparse.csr_matrix((np.concatenate(vv), (np.concatenate(rr), np.concatenate(cc))), shape=(self.N,self.npar)))
        self.D = np.array([self.m.bs,self.m.bq,self.m.wt,self.m.wq,self.m.c])
        over = b.over.to_numpy()
        ball = 6*over+b.ball.to_numpy()
        pressure = np.zeros(self.N)
        c = chase > 0
        pressure[c] = self.m.pressure(b.target.to_numpy()[c],b.runs_before.to_numpy()[c],ball[c])
        self.offset = self.m.situation(over,b.position.to_numpy(),b.wickets_before.to_numpy(),chase,pressure)
        self.y = b.outcome.to_numpy()
        self.YD = self.D[:,self.y].T
        self.x = np.zeros(self.npar)

    def add(self,name,size,d,indices,values=None,variance=.1,temporal=False,fixed=False):
        start = self.npar
        self.npar += size
        self.groups[name] = dict(start=start,end=self.npar,size=size,variance=variance,temporal=temporal,fixed=fixed)
        self.terms[d].append((indices+start,np.ones(self.N) if values is None else values))

    def covariance(self,g):
        talent, form = g['variance']
        s = self.S
        # An annual form persistence; the persistent part is talent.
        return talent*np.ones((s,s)) + form*.55**np.abs(np.arange(s)[:,None]-np.arange(s)[None,:])

    def precision(self):
        blocks = []
        for g in self.groups.values():
            if g['temporal']:
                prec = linalg.inv(self.covariance(g))
                blocks.append(sparse.kron(sparse.eye(g['size']//self.S),sparse.csr_matrix(prec)))
            else:
                blocks.append(sparse.eye(g['size'])/g['variance'])
        return sparse.block_diag(blocks,format='csc')

    def probabilities(self,x):
        effect = np.column_stack([a@x for a in self.A])
        z = self.offset + effect@self.D
        mx = z.max(axis=1)
        e = np.exp(z-mx[:,None])
        den = e.sum(axis=1)
        p = e/den[:,None]
        loss = np.sum(np.log(den)+mx-z[np.arange(self.N),self.y])
        return loss,p

    def objective(self,x):
        loss,p = self.probabilities(x)
        err = p@self.D.T-self.YD
        grad = self.Q@x
        value = loss+.5*np.dot(x,grad)
        for d,a in enumerate(self.A):
            grad += a.T@err[:,d]
        return value,grad

    def hessian(self):
        _,p = self.probabilities(self.x)
        mean = p@self.D.T
        H = self.Q.copy()
        for i in range(5):
            for j in range(i,5):
                w = p@(self.D[i]*self.D[j])-mean[:,i]*mean[:,j]
                t = self.A[i].T@self.A[j].multiply(w[:,None])
                H += t if i==j else t+t.T
        return H.tocsc()

    def curvature_correction(self,C,p):
        """Derivative of half the log determinant, and the mean/mode correction."""
        mean = p@self.D.T
        # Posterior covariance of the five scalar ball effects.
        V = np.zeros((self.N,5,5))
        for i in range(5):
            for j in range(i,5):
                z = np.zeros(self.N)
                for ai,av in self.terms[i]:
                    for bi,bv in self.terms[j]:
                        z += av*bv*C[ai,bi]
                V[:,i,j] = z
                V[:,j,i] = z
        third = np.zeros((self.N,5))
        for k in range(6):
            delta = self.D[:,k]-mean
            t = np.einsum('ni,nij,nj->n',delta,V,delta,optimize=True)
            third += (p[:,k]*t)[:,None]*delta
        g = np.zeros(self.npar)
        for i in range(5):
            g += .5*(self.A[i].T@third[:,i])
        return C@g

    def fit(self,iterations=25):
        names = [name for name,g in self.groups.items() if not g['fixed']]
        initial = np.concatenate([np.atleast_1d(self.groups[k]['variance']) for k in names])
        # Weak variance priors stabilize effects with little information (splits,
        # individual venue preferences, and drift). Strongly observed effects
        # are determined by the marginal likelihood.
        prior_strength = []
        for k in names:
            prior_strength.extend([.35,.8] if self.groups[k]['temporal'] else [.5])
        prior_strength = np.array(prior_strength)
        evaluations = [0]
        def marginal(logvar):
            pos = 0
            for name in names:
                g = self.groups[name]
                n = 2 if g['temporal'] else 1
                g['variance'] = tuple(np.exp(logvar[pos:pos+n])) if n==2 else float(np.exp(logvar[pos]))
                pos += n
            self.Q = self.precision()
            t = time.monotonic()
            # Newton solves avoid loose stopping rules along nearly confounded
            # global directions in the multinomial likelihood.
            for newton in range(12):
                value, gradient = self.objective(self.x)
                H = self.hessian()
                L = linalg.cho_factor(H.toarray(),lower=True,check_finite=False)
                step = linalg.cho_solve(L,gradient,check_finite=False)
                decrement = gradient@step
                if decrement < 1e-9:
                    break
                rate = 1.
                while rate > .001:
                    candidate = self.x-rate*step
                    if self.objective(candidate)[0] < value-.01*rate*decrement:
                        self.x = candidate
                        break
                    rate *= .5
            if decrement >= 1e-9:
                L = linalg.cho_factor(self.hessian().toarray(),lower=True,check_finite=False)
            mode_value = self.objective(self.x)[0]
            C = linalg.cho_solve(L,np.eye(self.npar),check_finite=False)
            _,p = self.probabilities(self.x)
            correction = self.curvature_correction(C,p)
            logdetH = 2*np.log(np.diag(L[0])).sum()
            logdetQ = 0.
            grad = []
            for name,g in self.groups.items():
                a,e = g['start'],g['end']
                if g['temporal']:
                    n = g['size']//self.S
                    K = self.covariance(g)
                    Ki = linalg.inv(K)
                    logdetQ -= n*np.linalg.slogdet(K)[1]
                    xx = self.x[a:e].reshape(n,self.S)
                    uu = correction[a:e].reshape(n,self.S)
                    ids = np.arange(a,e).reshape(n,self.S)
                    moment = xx.T@xx - uu.T@xx - xx.T@uu + C[ids[:,:,None],ids[:,None,:]].sum(axis=0)
                    for derivative in (g['variance'][0]*np.ones((self.S,self.S)),g['variance'][1]*.55**np.abs(np.arange(self.S)[:,None]-np.arange(self.S)[None,:])):
                        grad.append(.5*(n*np.trace(Ki@derivative)-np.trace(Ki@derivative@Ki@moment)))
                else:
                    logdetQ -= g['size']*np.log(g['variance'])
                    if not g['fixed']:
                        moment = np.sum(self.x[a:e]**2-2*self.x[a:e]*correction[a:e]+np.diag(C)[a:e])
                        grad.append(.5*(g['size']-moment/g['variance']))
            delta = logvar-np.log(initial)
            value = mode_value+.5*(logdetH-logdetQ)+.5*np.sum(prior_strength*delta**2)
            grad = np.array(grad)+prior_strength*delta
            self.last_logvar = logvar.copy()
            self.C = C
            self.mean_correction = correction
            self.L = L
            evaluations[0] += 1
            if self.verbose:
                values = [(name,np.round(self.groups[name]['variance'],4)) for name in names]
                print('evidence',evaluations[0],round(value,3),'gradient',round(np.linalg.norm(grad),3),'seconds',round(time.monotonic()-t,1),values,file=sys.stderr,flush=True)
            return value,grad
        res = optimize.minimize(marginal,np.log(initial),jac=True,method='L-BFGS-B',bounds=[(np.log(.00015),np.log(1.5))]*len(initial),options={'maxiter':iterations,'ftol':2e-9,'gtol':.015,'maxls':10})
        if not np.array_equal(self.last_logvar,res.x):
            marginal(res.x)
        self.hyper_result = res
        self.posterior_diag = np.diag(self.C)
        return self

    def value(self,name):
        g = self.groups[name]
        return self.x[g['start']:g['end']]

    def future(self,name):
        g = self.groups[name]
        a,b = g['variance']
        cross = a+b*.55**(self.S-np.arange(self.S))
        weights = linalg.solve(self.covariance(g),cross,assume_a='pos')
        return self.value(name).reshape(-1,self.S)@weights

    def book(self):
        p,v = self.h.players,self.h.venues
        style = self.value('style')+self.value('bat_mean')[p.role]+self.value('bat_global')[0]
        quality = self.future('quality')+self.value('quality_mean')[p.role]+self.value('quality_global')[0]
        kind = self.value('kind_mean')[p.style].copy()
        kind[self.bowlers] += self.value('kind')
        bq = self.value('bowl_mean')[p.role].copy()+self.value('bowl_global')[0]
        bq[self.bowlers] += self.future('bowl_quality')
        return SkillBook(p,v,style,quality,self.value('split'),kind,bq,
            self.value('type').reshape(2,2),self.value('pitch').reshape(2,3),
            self.value('venue'),self.value('dew')+self.value('chase_mean')[0],
            self.value('affinity').reshape(self.P,self.V),self.value('home')[0],
            self.value('era')[-1],np.sqrt(self.groups['day']['variance']),0.)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--league',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--verbose',action='store_[REDACTED]')
    parser.add_argument('--samples',type=int,default=65536)
    args = parser.parse_args()
    h,fixtures = load_league(args.league)
    fit = Estimator(h,args.verbose).fit()
    from predict import Predictive
    sim = Predictive(fit,draws=1024)
    rows = []
    for f in fixtures:
        q = sim.probability(f,args.samples,90210+f.match)
        rows.append((f.match,q))
        if args.verbose:
            print('fixture',f.match,round(q,5),file=sys.stderr,flush=True)
    result = pd.DataFrame(rows,columns=['fixture','p_home'])
    result.p_home = result.p_home.clip(.002,.998)
    Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    result.to_csv(args.out,index=False)

if __name__ == '__main__':
    main()
