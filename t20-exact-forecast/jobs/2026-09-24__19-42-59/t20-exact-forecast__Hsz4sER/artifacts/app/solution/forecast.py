"""Empirical Bayes inference for the public ball model, followed by match simulation."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '2'
os.environ['OMP_NUM_THREADS'] = '2'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import time
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import minimize
from scipy.sparse.linalg import splu
from engine.model import load_public_model, SkillBook, MatchSimulator
from engine.league_io import load_league

class Fit:
    def __init__(self, history, model):
        self.h, self.model = history, model
        b, p, v = history.balls, history.players, history.venues
        self.n, self.np, self.nv = len(b), len(p.role), len(v.pitch)
        self.ns = int(b.season.max()) + 1
        self.nt = self.ns * 2
        self.times = np.arange(self.nt)//2*12 + np.arange(self.nt)%2*4 + 1.5
        self.future = self.ns*12
        self.d = np.array([model.bs, model.bq, model.wt, model.wq, model.c])
        self.y = b.outcome.to_numpy()
        bat, bowl, ven = (b[c].to_numpy() for c in ('batter','bowler','venue'))
        self.bowlers = np.flatnonzero(p.role != 0)
        # All actual bowlers are included even if the role taxonomy changes.
        self.bowlers = np.union1d(self.bowlers, np.unique(bowl))
        self.nb = len(self.bowlers)
        self.bowlmap = np.zeros(self.np, int); self.bowlmap[self.bowlers] = np.arange(self.nb)
        bi = self.bowlmap[bowl]
        match_ids = history.matches.match.to_numpy()
        matchmap = {m:i for i,m in enumerate(match_ids)}
        mi = np.array([matchmap[m] for m in b.match])
        weeks = history.matches.week.to_numpy()[mi]
        period = b.season.to_numpy()*2 + (weeks >= 4)
        second = (b.innings.to_numpy() == 2).astype(float)
        pres = np.zeros(self.n)
        sel = second > 0
        pres[sel] = model.pressure(b.target.to_numpy()[sel], b.runs_before.to_numpy()[sel], (b.over*6+b.ball).to_numpy()[sel])
        self.offset = model.situation(b.over.to_numpy(), b.position.to_numpy(), b.wickets_before.to_numpy(), second, pres)
        self.groups = {}; self.pdim = 0
        self.rows, self.cols, self.values = [[] for _ in range(5)], [[] for _ in range(5)], [[] for _ in range(5)]
        self.add('style_mean', 3, 0, p.role[bat], sd=1.)
        self.add('style', self.np, 0, bat, sd=.28, learn=True)
        self.add('quality_mean', 3, 1, p.role[bat], sd=1.)
        self.add('quality', self.np*self.nt, 1, bat*self.nt+period, sd=.3, temporal=True, learn=True)
        self.add('split', self.np, 1, bat, np.where(p.style[bowl]==0,.5,-.5), sd=.16, learn=True)
        self.add('kind_mean', 2, 2, p.style[bowl], sd=.6)
        self.add('kind', self.nb, 2, bi, sd=.22, learn=True)
        self.add('bowling_mean', 2, 3, p.role[bowl]-1, sd=1.)
        self.add('bowling', self.nb*self.nt, 3, bi*self.nt+period, sd=.25, temporal=True, learn=True)
        self.add('venue', self.nv, 4, ven, sd=.2, learn=True)
        self.add('era', self.ns, 4, b.season.to_numpy(), sd=.4)
        self.add('dew', self.nv, 4, ven, second, sd=.12, learn=True)
        self.add('chase', 1, 4, np.zeros(self.n, int), second, sd=.3)
        self.add('home', 1, 4, np.zeros(self.n, int), (v.home_team[ven] == b.batting_team.to_numpy()).astype(float), sd=.3)
        self.add('affinity', self.np*self.nv, 4, bat*self.nv+ven, sd=.10, learn=True)
        self.add('day', len(match_ids), 4, mi, sd=.14, learn=True)
        self.add('hand_type', 4, 4, p.hand[bat]*2+p.style[bowl], sd=.10)
        self.add('pitch_type', 6, 4, p.style[bowl]*3+v.pitch[ven], sd=.10)
        self.X = [sparse.csr_matrix((np.concatenate(self.values[k]), (np.concatenate(self.rows[k]), np.concatenate(self.cols[k]))), shape=(self.n,self.pdim)) for k in range(5)]
        self.Z = sparse.vstack(self.X).tocsr()
        self.theta = np.zeros(self.pdim)
        self.update_prior()

    def add(self, name, size, direction, index, value=None, sd=.2, learn=False, temporal=False):
        start = self.pdim; self.pdim += size
        g = dict(start=start, size=size, sl=slice(start,self.pdim), sd=sd, learn=learn, temporal=temporal)
        if temporal:
            g.update(talent=sd, form=.14, length=8.)
        self.groups[name] = g
        value = np.ones(self.n) if value is None else value
        keep = value != 0
        self.rows[direction].append(np.flatnonzero(keep)); self.cols[direction].append(index[keep]+start); self.values[direction].append(value[keep])

    def covariance(self, g):
        dt = np.abs(self.times[:,None]-self.times[None,:])
        return g['talent']**2 + g['form']**2*np.exp(-dt/g['length']) + np.eye(self.nt)*1.e-8

    def update_prior(self):
        blocks=[]
        for g in self.groups.values():
            if g['temporal']:
                g['cov'] = self.covariance(g); g['prec'] = np.linalg.inv(g['cov'])
                blocks.append(sparse.kron(sparse.eye(g['size']//self.nt), g['prec'], format='csr'))
            else:
                blocks.append(sparse.eye(g['size'],format='csr')/g['sd']**2)
        self.P = sparse.block_diag(blocks, format='csr')

    def probabilities(self, x):
        effects = np.asarray(self.Z @ x).reshape(5,self.n).T
        z = self.offset + effects @ self.d
        mx = z.max(axis=1)
        exp = np.exp(z-mx[:,None]); sums=exp.sum(axis=1)
        prob = exp/sums[:,None]
        loss = (np.log(sums)+mx-z[np.arange(self.n),self.y]).sum()
        return prob,loss

    def objective(self, scaled):
        x = scaled*self.scale
        prob, loss = self.probabilities(x)
        prob[np.arange(self.n), self.y] -= 1
        grad = self.Z.T @ (prob @ self.d.T).T.ravel() + self.P@x
        return loss+.5*x@(self.P@x), np.asarray(grad)*self.scale

    def optimize(self):
        if not hasattr(self, 'lik_diag'):
            self.lik_diag = np.asarray(self.Z.power(2).sum(axis=0)).ravel()*.15
        self.scale = 1/np.sqrt(self.P.diagonal()+self.lik_diag)
        opt = minimize(self.objective, self.theta/self.scale, jac=True, method='L-BFGS-B', options={'maxiter':180,'ftol':2e-12,'gtol':1e-5,'maxcor':25})
        self.theta = opt.x*self.scale
        return opt.fun, opt.nit

    def hessian(self):
        prob, _ = self.probabilities(self.theta)
        mean = prob @ self.d.T
        H = self.P.copy()
        for j in range(5):
            for k in range(j+1):
                w = prob @ (self.d[j]*self.d[k]) - mean[:,j]*mean[:,k]
                block = self.X[j].T @ self.X[k].multiply(w[:,None])
                H = H+block if j==k else H+block+block.T
        self.lik_diag = H.diagonal()-self.P.diagonal()
        return H.tocsc()

    def empirical_bayes(self, rounds=7, verbose=True):
        rng=np.random.default_rng(78342)
        probes=rng.choice([-1.,1.], size=(self.pdim,48))
        for it in range(rounds):
            tick=time.time(); loss,nit=self.optimize()
            H=self.hessian(); lu=splu(H)
            invprobes=lu.solve(probes)
            self.postdiag=np.maximum(np.mean(probes*invprobes,axis=1), 1e-8)
            for name,g in self.groups.items():
                if not g['learn']: continue
                mu=self.theta[g['sl']]
                if g['temporal']:
                    count=g['size']//self.nt
                    a=probes[g['sl']].reshape(count,self.nt,-1)
                    b=invprobes[g['sl']].reshape(count,self.nt,-1)
                    vv=np.einsum('itr,iur->tu',a,b)/(count*a.shape[2]); vv=(vv+vv.T)/2
                    mu=mu.reshape(count,self.nt)
                    moment=mu.T@mu/count+vv
                    def obj(logpars):
                        talent,form,length=np.exp(logpars)
                        cov=talent**2+form**2*np.exp(-np.abs(self.times[:,None]-self.times[None,:])/length)+np.eye(self.nt)*1e-8
                        val=count*(np.linalg.slogdet(cov)[1]+np.trace(np.linalg.solve(cov,moment)))
                        # Weak regularization of the poorly identified drift timescale.
                        val+=((logpars[2]-np.log(8.))/0.7)**2*2
                        return val
                    pars=minimize(obj,np.log([g['talent'],g['form'],g['length']]),method='L-BFGS-B',bounds=[(np.log(.025),np.log(1.)),(np.log(.025),np.log(.5)),(np.log(2),np.log(40))])
                    g['talent'],g['form'],g['length']=np.exp(pars.x)
                else:
                    moment=np.mean(mu**2+self.postdiag[g['sl']])
                    # Two prior observations keep small ground groups stable.
                    weight=2 if g['size'] < 30 else 1
                    init={'style':.28,'split':.16,'kind':.22,'venue':.2,'dew':.12,'affinity':.1,'day':.14}[name]
                    var=(moment*g['size']+weight*init**2)/(g['size']+weight)
                    g['sd']=np.sqrt(np.clip(var,.02**2,.8**2))
            if verbose:
                info={k:tuple(round(g[z],3) for z in ('talent','form','length')) if g['temporal'] else round(g['sd'],3) for k,g in self.groups.items() if g['learn']}
                print('fit',it,'loss',round(loss,1),'iterations',nit,'seconds',round(time.time()-tick,1),info, file=sys.stderr,flush=True)
            self.update_prior()
        self.optimize()

    def get(self,name): return self.theta[self.groups[name]['sl']]

    def future_quality(self,name):
        g=self.groups[name]
        cov=self.covariance(g)
        cross=g['talent']**2 + g['form']**2*np.exp(-np.abs(self.future-self.times)/g['length'])
        weights=np.linalg.solve(cov,cross)
        return self.get(name).reshape(-1,self.nt)@weights

    def book(self):
        p,v=self.h.players,self.h.venues
        bq=np.zeros(self.np); kind=np.zeros(self.np)
        bq[self.bowlers]=self.future_quality('bowling')+self.get('bowling_mean')[p.role[self.bowlers]-1]
        kind[self.bowlers]=self.get('kind')+self.get('kind_mean')[p.style[self.bowlers]]
        era=self.get('era')[-1]
        return SkillBook(p,v,self.get('style')+self.get('style_mean')[p.role],self.future_quality('quality')+self.get('quality_mean')[p.role],self.get('split'),kind,bq,self.get('hand_type').reshape(2,2),-self.get('pitch_type').reshape(2,3),self.get('venue'),self.get('dew')+self.get('chase')[0],self.get('affinity').reshape(self.np,self.nv),self.get('home')[0],era,self.groups['day']['sd'],0.)

def main():
    from inference import marginal_fit, predictive_draws
    from simulation import PredictiveSimulator
    parser=argparse.ArgumentParser();parser.add_argument('--league',required=True);parser.add_argument('--out',required=True)
    parser.add_argument('--simulations',type=int,default=65536)
    args=parser.parse_args()
    start=time.time(); history, fixtures=load_league(args.league); model=load_public_model()
    fit=Fit(history,model);fit.empirical_bayes(rounds=6)
    marginal_fit(fit,maxiter=30)
    sim=PredictiveSimulator(fit,predictive_draws(fit)); probs=[]
    for f in fixtures:
        prob=sim.probability(f,args.simulations,seed=9201+f.match)
        probs.append(prob)
        print('fixture',f.match,round(prob,5),'elapsed',round(time.time()-start,1),file=sys.stderr,flush=True)
    Path(args.out).parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame({'fixture':[f.match for f in fixtures],'p_home':np.clip(probs,.002,.998)}).to_csv(args.out,index=False)

if __name__=='__main__':main()
