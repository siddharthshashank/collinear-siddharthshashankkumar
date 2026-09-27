"""Penalized likelihood and empirical Bayes for the public ball model."""
import time
import numpy as np
from scipy import sparse, optimize, linalg

class Fit:
    def __init__(self, history, model, periods=1):
        self.h, self.m = history, model
        b = history.balls
        self.n = len(b)
        self.P = len(history.players.role)
        self.V = len(history.venues.pitch)
        self.seasons = int(b.season.max())+1
        self.periods = periods
        self.S = self.seasons * periods
        self.times = np.repeat(np.arange(self.seasons), periods) + np.tile(np.arange(periods), self.seasons) * (2./3.) / periods
        self.future = self.seasons - (4./periods - .5)/12.
        self.groups = {}
        self.size = 0
        self.features = []
        pl = history.players
        bat, bowl, venue, season = [b[k].to_numpy() for k in ['batter','bowler','venue','season']]
        weeks = b.match.map(history.matches.set_index('match').week).to_numpy()
        skill_time = season * periods + np.minimum((weeks * periods // 8).astype(int), periods-1)
        self.bowling_ids = np.unique(bowl)
        bi = np.searchsorted(self.bowling_ids, bowl)
        self.B = len(self.bowling_ids)
        chasing = (b.innings.to_numpy()==2).astype(float)
        home = (b.batting_team.to_numpy()==history.venues.home_team[venue]).astype(float)
        sign = np.where(pl.style[bowl]==0, .5, -.5)
        over = b.over.to_numpy()
        ball = over*6 + b.ball.to_numpy()
        pressure = np.where(chasing, model.pressure(b.target.to_numpy(),b.runs_before.to_numpy(),ball),0.)
        self.offset = model.situation(over,b.position.to_numpy(),b.wickets_before.to_numpy(),chasing,pressure)
        self.y = b.outcome.to_numpy()
        self.dirs = np.array([model.bs,model.bq,model.wt,model.wq,model.c])
        self.add('style_mean',3,pl.role[bat],0,sd=.5,learn=False)
        self.add('style',self.P,bat,0,sd=.45)
        self.add('quality_mean',3,pl.role[bat],1,sd=1.,learn=False)
        self.add('quality',self.P*self.S,bat*self.S+skill_time,1,sd=.5,temporal=True)
        self.add('split',self.P,bat,1,values=sign,sd=.2)
        self.add('kind_mean',2,pl.style[bowl],2,sd=.5,learn=False)
        self.add('kind',self.B,bi,2,sd=.3)
        self.add('bowl_mean',3,pl.role[bowl],3,sd=.7,learn=False)
        self.add('bowling',self.B*self.S,bi*self.S+skill_time,3,sd=.4,temporal=True)
        self.add('venue',self.V,venue,4,sd=.2)
        self.add('era',self.seasons,season,4,sd=.4,learn=False)
        self.add('dew_mean',1,np.zeros(self.n,int),4,values=chasing,sd=.2,learn=False)
        self.add('dew',self.V,venue,4,values=chasing,sd=.12)
        self.add('home',1,np.zeros(self.n,int),4,values=home,sd=.2,learn=False)
        self.add('affinity',self.P*self.V,bat*self.V+venue,4,sd=.15)
        self.add('hand',4,pl.hand[bat]*2+pl.style[bowl],4,sd=.08,learn=False)
        self.add('pitch',6,pl.style[bowl]*3+history.venues.pitch[venue],4,sd=.08,learn=False)
        self.matchids, mi = np.unique(b.match.to_numpy(),return_inverse=True)
        self.add('day',len(self.matchids),mi,4,sd=.15)
        rows, cols, vals = [],[],[]
        for ix, dim, val in self.features:
            rows.append(np.arange(self.n)*5+dim);cols.append(ix);vals.append(val)
        self.X = sparse.csr_matrix((np.concatenate(vals),(np.concatenate(rows),np.concatenate(cols))),shape=(self.n*5,self.size))
        self.XT = self.X.T.tocsr()
        self.theta = np.zeros(self.size)
        self.form = {'quality':.22, 'bowling':.18}
        self.rho = .45
        self.last_cov = None

    def add(self,name,size,ids,dim,values=None,sd=.2,learn=True,temporal=False):
        start = self.size; self.size += size
        self.groups[name] = dict(start=start,stop=self.size,sd=sd,learn=learn,temporal=temporal)
        values = np.ones(self.n) if values is None else values
        self.features.append((ids+start,dim,values))

    def prior(self):
        Q = sparse.lil_matrix((self.size,self.size))
        for name,g in self.groups.items():
            a,z = g['start'],g['stop']
            if g['temporal']:
                K = self.kernel(name)
                block = sparse.kron(sparse.eye((z-a)//self.S),np.linalg.inv(K),format='csr')
                Q[a:z,a:z] = block
            else:
                Q[a:z,a:z] = sparse.eye(z-a)/g['sd']**2
        return Q.tocsr()

    def kernel(self,name):
        s = self.times
        return self.groups[name]['sd']**2 + self.form[name]**2*self.rho**np.abs(s[:,None]-s)

    def likelihood(self,theta, Q, need_hess=False):
        eta = (self.X @ theta).reshape(self.n,5)
        logits = self.offset + eta @ self.dirs
        peak = logits.max(1)
        p = np.exp(logits-peak[:,None]); total=p.sum(1);p/=total[:,None]
        value = np.sum(np.log(total)+peak-logits[np.arange(self.n),self.y])+.5*theta@(Q@theta)
        if need_hess:
            means = p@self.dirs.T
            weights = np.einsum('ni,di,ei->nde',p,self.dirs,self.dirs,optimize=True)-means[:,:,None]*means[:,None,:]
            R = sparse.bsr_matrix((weights,np.arange(self.n),np.arange(self.n+1)),shape=(self.n*5,self.n*5))
            H = self.XT @ (R @ self.X) + Q
            return value,p,H
        p[np.arange(self.n),self.y]-=1
        grad = self.XT@(p@self.dirs.T).ravel()+Q@theta
        return value,grad

    def fit(self,steps=6,verbose=True):
        started=time.time()
        for iteration in range(steps):
            Q=self.prior()
            # Prior whitening gives comparable curvature across sparse and common effects.
            scale=1/np.sqrt(Q.diagonal()+.5*np.asarray(self.X.power(2).sum(0)).ravel()/5)
            def fun(x):
                v,g=self.likelihood(x*scale,Q)
                return v,g*scale
            result=optimize.minimize(fun,self.theta/scale,jac=True,method='L-BFGS-B',options={'maxiter':130,'ftol':1e-9,'gtol':.005,'maxcor':15})
            self.theta=result.x*scale
            val,p,H=self.likelihood(self.theta,Q,True)
            # Exact joint Laplace covariance includes confounding between all effects.
            self.last_cov = None
            cov = None
            dense = H.toarray(order='F')
            factor = linalg.cho_factor(dense, lower=True, overwrite_a=True, check_finite=False)
            cov = linalg.cho_solve(factor, np.eye(self.size, order='F'), overwrite_b=True, check_finite=False)
            del dense, factor, H
            self.last_cov=cov
            if verbose: print('fit',iteration,'nll',round(val,2),'seconds',round(time.time()-started,1),'iterations',result.nit,flush=True)
            if iteration == steps-1: break
            diag=np.diag(cov).copy()
            for name,g in self.groups.items():
                if not g['learn']: continue
                a,z=g['start'],g['stop'];x=self.theta[a:z]
                if g['temporal']:
                    count=(z-a)//self.S
                    xx=x.reshape(count,self.S)
                    moment=xx.T@xx/count
                    for k in range(count): moment+=cov[a+k*self.S:a+(k+1)*self.S,a+k*self.S:a+(k+1)*self.S]/count
                    def obj(v):
                        K=np.exp(2*v[0])+np.exp(2*v[1])*self.rho**np.abs(self.times[:,None]-self.times)
                        return np.linalg.slogdet(K)[1]+np.trace(np.linalg.solve(K,moment))
                    r=optimize.minimize(obj,np.log([g['sd'],self.form[name]]),method='L-BFGS-B',bounds=[(np.log(.08),np.log(1.2)),(np.log(.06),np.log(.65))])
                    g['sd'],self.form[name]=np.exp(r.x)
                else:
                    g['sd']=float(np.clip(np.sqrt(np.mean(x*x+diag[a:z])),.035,.9))
            if verbose: print('scales',{n:round(g['sd'],3) for n,g in self.groups.items() if g['learn']},'form',self.form,flush=True)
        return self

    def values(self,name):
        g=self.groups[name]
        return self.theta[g['start']:g['stop']]

    def next_quality(self,name):
        # Conditional mean at the start of next season; partial persistence of form.
        K=self.kernel(name)
        cross=self.groups[name]['sd']**2+self.form[name]**2*self.rho**(self.future-self.times)
        weights=np.linalg.solve(K,cross)
        return self.values(name).reshape(-1,self.S)@weights

    def book(self):
        from engine.model import SkillBook
        p,v=self.h.players,self.h.venues
        kind=np.zeros(self.P); bowl=np.zeros(self.P)
        kind[self.bowling_ids]=self.values('kind')+self.values('kind_mean')[p.style[self.bowling_ids]]
        bowl[self.bowling_ids]=self.next_quality('bowling')+self.values('bowl_mean')[p.role[self.bowling_ids]]
        return SkillBook(p,v,self.values('style')+self.values('style_mean')[p.role],
            self.next_quality('quality')+self.values('quality_mean')[p.role],self.values('split'),kind,bowl,
            self.values('hand').reshape(2,2),-self.values('pitch').reshape(2,3),self.values('venue'),
            self.values('dew')+self.values('dew_mean')[0],self.values('affinity').reshape(self.P,self.V),
            self.values('home')[0],self.values('era')[-1],self.groups['day']['sd'],0.)

    def posterior_mean(self):
        """First Laplace skew correction, important for infrequent batters."""
        theta=self.theta
        logits=self.offset+(self.X@theta).reshape(self.n,5)@self.dirs
        p=np.exp(logits-logits.max(1,keepdims=True));p/=p.sum(1,keepdims=True)
        coeff_cov=np.zeros((self.n,5,5))
        for j,(ix,dim,val) in enumerate(self.features):
            for k in range(j+1):
                iy,dim2,val2=self.features[k]
                cc=self.last_cov[ix,iy]*val*val2
                coeff_cov[:,dim,dim2]+=cc
                if j!=k:coeff_cov[:,dim2,dim]+=cc
        variance=np.einsum('nde,di,ei->ni',coeff_cov,self.dirs,self.dirs,optimize=True)
        means=p@self.dirs.T
        cross=np.einsum('nde,ne->nd',coeff_cov,means)
        t=variance-2*cross@self.dirs
        dp=.5*p*(t-(p*t).sum(1,keepdims=True))
        grad=self.XT@(dp@self.dirs.T).ravel()
        return theta-self.last_cov@grad
