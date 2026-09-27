"""Empirical Bayes inference for the public six-outcome ball model."""
import numpy as np
from scipy import sparse, linalg, optimize
from scipy.special import logsumexp
import time

class Fitter:
    def __init__(self, history, model):
        self.h, self.model = history, model
        b = history.balls
        self.n = n = len(b)
        self.np = len(history.players.role)
        self.ns = int(b.season.max()) + 1
        self.nv = len(history.venues.pitch)
        self.bowlers = np.unique(b.bowler)
        self.nb = len(self.bowlers)
        self.bmap = np.zeros(self.np, int)
        self.bmap[self.bowlers] = np.arange(self.nb)
        self.matches, match = np.unique(b.match, return_inverse=True)
        self.affs, aff = np.unique(b.batter.to_numpy()*self.nv + b.venue.to_numpy(), return_inverse=True)
        self.groups = {}
        self.size = 0
        self.parts = [[] for _ in range(5)]
        bat, bowl, venue, season = (b[c].to_numpy() for c in ['batter','bowler','venue','season'])
        role = history.players.role
        how = history.players.style[bowl]
        hand = history.players.hand[bat]
        chasing = (b.innings.to_numpy() == 2).astype(float)
        home = (history.venues.home_team[venue] == b.batting_team.to_numpy()).astype(float)
        self.add('style', self.np, 0, bat, sd=.35)
        self.add('bat', self.np*self.ns, 1, bat*self.ns+season, sd=.3, dynamic=True)
        self.add('split', self.np, 1, bat, np.where(how==0,.5,-.5), sd=.18)
        self.add('kind', self.nb, 2, self.bmap[bowl], sd=.25)
        self.add('bowl', self.nb*self.ns, 3, self.bmap[bowl]*self.ns+season, sd=.25, dynamic=True)
        self.add('affinity', len(self.affs), 4, aff, sd=.12)
        self.add('day', len(self.matches), 4, match, sd=.15)
        self.add('venue', self.nv, 4, venue, sd=.2)
        self.add('dew', self.nv, 4, venue, chasing, sd=.12)
        self.add('era', self.ns, 4, season, sd=.4, fixed=True)
        self.add('chase', 1, 4, np.zeros(n,int), chasing, sd=.4, fixed=True)
        self.add('home', 1, 4, np.zeros(n,int), home, sd=.4, fixed=True)
        self.add('type_table',4,4,hand*2+how,sd=.07)
        self.add('pitch_table',6,4,how*3+history.venues.pitch[venue],sd=.07)
        self.add('style_mean',3,0,role[bat],sd=.7,fixed=True)
        self.add('bat_mean',3,1,role[bat],sd=.7,fixed=True)
        self.add('kind_mean',2,2,how,sd=.7,fixed=True)
        self.add('bowl_mean',3,3,role[bowl],sd=.7,fixed=True)
        self.A=[]
        for parts in self.parts:
            rows,cols,vals = zip(*parts)
            self.A.append(sparse.csr_matrix((np.concatenate(vals),(np.concatenate(rows),np.concatenate(cols))),shape=(n,self.size)))
        self.dirs = np.array([model.bs,model.bq,model.wt,model.wq,model.c])
        self.X = [sum(self.A[j]*self.dirs[j,k] for j in range(5)).tocsr() for k in range(6)]
        ball = b.over.to_numpy()*6+b.ball.to_numpy()
        pressure = model.pressure(b.target.to_numpy(),b.runs_before.to_numpy(),ball)*chasing
        self.base = model.situation(b.over.to_numpy(),b.position.to_numpy(),b.wickets_before.to_numpy(),chasing,pressure)
        self.y = b.outcome.to_numpy()
        self.ybase = self.base[np.arange(n),self.y].sum()
        self.xy = sum(x.T @ (self.y==k).astype(float) for k,x in enumerate(self.X))
        self.theta = np.zeros(self.size)
        self.trace=[]

    def add(self,name,count,direction,index,value=None,sd=.2,dynamic=False,fixed=False):
        start=self.size
        self.size+=count
        self.groups[name]=dict(start=start,end=self.size,sd=sd,dynamic=dynamic,fixed=fixed)
        if dynamic:
            self.groups[name]['hyper']=np.array([sd**2,.13**2,.4])
        values=np.ones(self.n) if value is None else value
        keep=values!=0
        self.parts[direction].append((np.arange(self.n)[keep],start+index[keep],values[keep]))

    def precision(self):
        P = np.zeros((self.size,self.size))
        for g in self.groups.values():
            s,e=g['start'],g['end']
            if not g['dynamic']:
                P[np.arange(s,e),np.arange(s,e)]=1/g['sd']**2
            else:
                t,f,r=g['hyper']
                C=t+f*r**np.abs(np.arange(self.ns)[:,None]-np.arange(self.ns))
                inv=linalg.inv(C)
                inds=np.arange(s,e).reshape(-1,self.ns)
                P[inds[:,:,None],inds[:,None,:]]=inv
        return P

    def evaluate(self,theta,P,hessian=False):
        z = self.base + np.column_stack([x@theta for x in self.X])
        lse = logsumexp(z,axis=1)
        p = np.exp(z-lse[:,None])
        pt=P@theta
        val = lse.sum()-self.ybase-self.xy@theta+.5*theta@pt
        grad = sum(x.T@p[:,k] for k,x in enumerate(self.X))-self.xy+pt
        if not hessian:
            return val,grad
        # Categorical Fisher information, without expanding ball/outcome pairs.
        EX = sum(x.multiply(p[:,k,None]) for k,x in enumerate(self.X)).tocsr()
        H = sum(x.T@x.multiply(p[:,k,None]) for k,x in enumerate(self.X))-EX.T@EX
        return val,grad,H.toarray()+P

    def map(self,P,maxiter=7):
        for it in range(maxiter):
            val,grad,H=self.evaluate(self.theta,P,True)
            cf=linalg.cho_factor(H,check_finite=False)
            step=linalg.cho_solve(cf,grad,check_finite=False)
            dec=grad@step
            if dec<.0001:
                return val,cf
            rate=1.
            while rate>.01:
                newval,_=self.evaluate(self.theta-rate*step,P)
                if newval < val:
                    self.theta-=rate*step
                    break
                rate*=.5
            if dec<.01:
                break
        val,grad,H=self.evaluate(self.theta,P,True)
        return val,linalg.cho_factor(H,check_finite=False)

    def fit(self,iterations=24,verbose=True):
        t0=time.time()
        for it in range(iterations):
            P=self.precision()
            val,cf=self.map(P,6 if it==0 else 3)
            V=linalg.cho_solve(cf,np.eye(self.size),check_finite=False)
            evidence=val+np.log(np.diag(cf[0])).sum()-.5*np.linalg.slogdet(P)[1]
            self.trace.append(evidence)
            change=0.
            for name,g in self.groups.items():
                if g['fixed']: continue
                s,e=g['start'],g['end']
                if not g['dynamic']:
                    moment=np.mean(self.theta[s:e]**2+np.diag(V)[s:e])
                    # Weak regularization of variance estimation, particularly for ten grounds.
                    # A few prior observations avoid extreme estimates with a small number of levels.
                    defaults={'style':.35,'split':.18,'kind':.25,'affinity':.12,'day':.15,'venue':.2,'dew':.12,'type_table':.07,'pitch_table':.07}
                    strength=2. if name in ('venue','dew','type_table','pitch_table') else .2
                    moment=(moment*(e-s)+strength*defaults[name]**2)/(e-s+strength)
                    sd=np.sqrt(moment)
                    change=max(change,abs(np.log(sd/g['sd'])))
                    g['sd']=sd
                else:
                    ids=np.arange(s,e).reshape(-1,self.ns)
                    means=self.theta[ids]
                    moment=np.mean(means[:,:,None]*means[:,None,:]+V[ids[:,:,None],ids[:,None,:]],axis=0)
                    n=len(ids)
                    dist=np.abs(np.arange(self.ns)[:,None]-np.arange(self.ns))
                    def obj(hyp):
                        t,f,r=np.exp(hyp[0]),np.exp(hyp[1]),hyp[2]
                        C=t+f*r**dist
                        sign,ld=np.linalg.slogdet(C)
                        # Regularize the poorly identified form persistence, mildly toward .4 per season.
                        loss=.5*n*(ld+np.trace(linalg.solve(C,moment,assume_a='pos')))
                        loss+=.5*((r-.4)/.3)**2
                        loss+=.3*(np.log(f/.13**2))**2
                        return loss
                    old=g['hyper']
                    res=optimize.minimize(obj,[np.log(old[0]),np.log(old[1]),old[2]],method='L-BFGS-B',bounds=[(-8,1),(-8,-.5),(.02,.95)])
                    new=np.r_[np.exp(res.x[:2]),res.x[2]]
                    change=max(change,np.max(abs(np.log(new[:2]/old[:2]))))
                    g['hyper']=new
            if verbose and (it%3==0 or it==iterations-1):
                params={k:np.round(v['hyper'],4).tolist() if v['dynamic'] else round(v['sd'],4) for k,v in self.groups.items() if not v['fixed']}
                print('fit',it,'evidence',round(evidence,2),'seconds',round(time.time()-t0,1),params,flush=True)
            if it>10 and change<.006: break
        P=self.precision()
        self.map_value,self.cf=self.map(P,4)
        self.cov= linalg.cho_solve(self.cf,np.eye(self.size),check_finite=False)
        return self

    def values(self,theta,name):
        g=self.groups[name]
        return theta[...,g['start']:g['end']]

    def forecast_values(self,theta,name,gen=None):
        g=self.groups[name]
        t,f,r=g['hyper']
        C=t+f*r**np.abs(np.arange(self.ns)[:,None]-np.arange(self.ns))
        c=t+f*r**(self.ns-np.arange(self.ns))
        weights=linalg.solve(C,c,assume_a='pos')
        v=self.values(theta,name).reshape(theta.shape[:-1]+(-1,self.ns))@weights
        if gen is not None:
            v+=gen.normal(size=v.shape)*np.sqrt(max(0,t+f-c@weights))
        return v
